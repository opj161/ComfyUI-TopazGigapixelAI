# gigapixel.py

import numpy as np
import os
# import pprint # Not used, can remove
import time
# import folder_paths # Not used directly in classes, but likely needed by ComfyUI globally
import torch
import subprocess
import json
import shutil

from PIL import Image, ImageOps
from typing import Optional

# --- GigapixelUpscaleSettings (Standard Models) ---
class GigapixelStandardSettings: # Renamed from GigapixelUpscaleSettings
    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'enabled': (['true', 'false'], {'default': 'true'}),
                'sharpen': ('FLOAT', {'default': 50, 'min': 0, 'max': 100, 'step': 1, 'display': 'Sharpen Strength (0-100)'}), # Default changed for example
                'denoise': ('FLOAT', {'default': 50, 'min': 0, 'max': 100, 'step': 1, 'display': 'Denoise Strength (0-100)'}), # Default changed for example
                'compression': ('FLOAT', {'default': 90, 'min': 0, 'max': 100, 'step': 1, 'display': 'Model Compression (--cm) (0-100)'}), # Default changed for example, assuming this is for JPEG output
                # Corrected 'fr' to 'face_recovery_strength'
                'face_recovery_strength': ('FLOAT', {'default': 0, 'min': 0, 'max': 100, 'step': 1, 'display': 'Face Recovery Strength (0-100)'}),
            },
        }

    RETURN_TYPES = ('GigapixelStandardSettings',) # Renamed
    RETURN_NAMES = ('standard_settings',) # Renamed
    FUNCTION = 'init'
    CATEGORY = 'image/GigapixelAI' # Added subcategory
    OUTPUT_NODE = False

    def init(self, enabled, sharpen, denoise, compression, face_recovery_strength):
        self.enabled = str(True).lower() == enabled.lower()
        self.sharpen = sharpen
        self.denoise = denoise
        self.compression = compression # Note: CLI uses --cm for model compression, not output JPEG quality. This might be a misunderstanding.
                                      # CLI uses --jq for jpeg quality. If this is for model compression, it's fine.
                                      # The doc mentions --cm/--compression for "various model options". Let's assume it's model compression.
        self.face_recovery_strength = face_recovery_strength
        return (self,)

# --- GigapixelModelSettings ---
class GigapixelModelSelection: # Renamed
    MODEL_MAPPING = {
        'Art & CG': 'art',
        'Lines': 'lines',
        'Very Compressed': 'vc',
        'High Fidelity': 'fidelity',
        'Low Resolution': 'lowres',
        'Standard': 'std',
        'Text & Shapes': 'text',
        'Recovery': 'recovery',  # New
        'Redefine': 'redefine'   # New
    }

    # Models that use --mv 2 by default (excluding recovery as it has its own mv setting)
    MV2_MODELS_DEFAULT = {'std', 'fidelity', 'lowres'} # 'recovery' removed, will be handled by its own settings

    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'model': (list(cls.MODEL_MAPPING.keys()), {'default': 'Standard'}),
            },
        }

    RETURN_TYPES = ('GigapixelModelSelection',) # Renamed
    RETURN_NAMES = ('model_selection',) # Renamed
    FUNCTION = 'init'
    CATEGORY = 'image/GigapixelAI'
    OUTPUT_NODE = False

    def init(self, model):
        self.model_name_ui = model # Keep UI name for potential use
        self.model_cli_code = self.MODEL_MAPPING[model]
        # This specific flag is now less relevant here, --mv will be handled more dynamically
        self.is_default_mv2_model = self.model_cli_code in self.MV2_MODELS_DEFAULT
        return (self,)

# --- GigapixelRecoverySettings (New Node) ---
class GigapixelRecoverySettings:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'model_version': ([1, 2], {'default': 2, 'display': 'Model Version (--mv)'}),
                'detail': ('FLOAT', {'default': 50, 'min': 1, 'max': 100, 'step': 1, 'display': 'Detail (1-100)'}),
                'face_recovery_version': ([1, 2], {'default': 2, 'display': 'Face Recovery Version (--frv)'}),
                'face_recovery_creativity': ([0, 1], {'default': 0, 'display': 'Face Recovery Creativity (0 or 1, --frc)'}),
            },
        }
    RETURN_TYPES = ('GigapixelRecoverySettings',)
    RETURN_NAMES = ('recovery_settings',)
    FUNCTION = 'init'
    CATEGORY = 'image/GigapixelAI'
    OUTPUT_NODE = False

    def init(self, model_version, detail, face_recovery_version, face_recovery_creativity):
        self.model_version = model_version
        self.detail = detail
        self.face_recovery_version = face_recovery_version
        self.face_recovery_creativity = face_recovery_creativity
        return (self,)

# --- GigapixelRedefineSettings (New Node) ---
class GigapixelRedefineSettings:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'creativity': ('INT', {'default': 3, 'min': 1, 'max': 6, 'step': 1, 'display': 'Creativity (--cr, 1-6)'}),
                'texture': ('INT', {'default': 3, 'min': 1, 'max': 6, 'step': 1, 'display': 'Texture (--tx, 1-6)'}),
                'prompt': ('STRING', {'default': '', 'multiline': True, 'display': 'Prompt'}),
                'denoise': ('INT', {'default': 3, 'min': 1, 'max': 6, 'step': 1, 'display': 'Denoise (--denoise, 1-6)'}),
                'sharpen': ('INT', {'default': 3, 'min': 1, 'max': 6, 'step': 1, 'display': 'Sharpen (--sharpen, 1-6)'}),
            },
        }
    RETURN_TYPES = ('GigapixelRedefineSettings',)
    RETURN_NAMES = ('redefine_settings',)
    FUNCTION = 'init'
    CATEGORY = 'image/GigapixelAI'
    OUTPUT_NODE = False

    def init(self, creativity, texture, prompt, denoise, sharpen):
        self.creativity = creativity
        self.texture = texture
        self.prompt = prompt
        self.denoise = denoise
        self.sharpen = sharpen
        return (self,)


# --- GigapixelAI (Main Node - Updated) ---
class GigapixelAI:
    def __init__(self):
        self.this_dir = os.path.dirname(os.path.abspath(__file__))
        self.comfy_dir = os.path.abspath(os.path.join(self.this_dir, '..', '..'))
        # Consider making output_dir configurable or truly temporary if batch_dir is always cleaned up
        self.output_dir = os.path.join(self.comfy_dir, 'temp', 'gigapixel_output') # This is a base, actual output is in batch_dir

    @classmethod
    def INPUT_TYPES(cls):
        return {
            'required': {
                'images': ('IMAGE',),
                'scale': ('FLOAT', {'default': 2.0, 'min': 1, 'max': 16, 'step': 0.1, 'round': False}), # Added step
                'no_temp_cleanup': (['true', 'false'], {'default': 'true', 'display': 'Clean Up Temp Files'}), # Renamed for clarity
            },
            'optional': {
                'gigapixel_exe': ('STRING', {'default': '', 'multiline': False, 'display': 'Gigapixel Executable Path'}),
                'model_selection': ('GigapixelModelSelection',), # Renamed
                'standard_settings': ('GigapixelStandardSettings',), # Renamed
                'recovery_settings': ('GigapixelRecoverySettings',), # New
                'redefine_settings': ('GigapixelRedefineSettings',), # New
            },
            "hidden": {}
        }

    RETURN_TYPES = ('STRING', 'STRING', 'IMAGE')
    # Corrected OUTPUT_IS_LIST based on plan
    RETURN_NAMES = ('settings_json', 'image_paths', 'IMAGE')
    FUNCTION = 'upscale_image'
    CATEGORY = 'image/GigapixelAI' # Main category
    OUTPUT_NODE = True
    OUTPUT_IS_LIST = (False, True, False) # Updated as per plan analysis

    def save_image(self, img_tensor, output_dir, filename_prefix, idx):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Convert tensor to PIL Image
        i = 255.0 * img_tensor.cpu().numpy()
        img_pil = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

        # Save image (e.g. as PNG)
        file_path = os.path.join(output_dir, f"{filename_prefix}_{idx}.png")
        img_pil.save(file_path)
        return file_path

    def load_image(self, image_path):
        i = Image.open(image_path)
        i = ImageOps.exif_transpose(i)
        image = i.convert('RGB')
        image = np.array(image).astype(np.float32) / 255.0
        image = torch.from_numpy(image)[None,]
        return image

    def upscale_image(self, images, scale, no_temp_cleanup,
                      gigapixel_exe=None,
                      model_selection: Optional[GigapixelModelSelection]=None,
                      standard_settings: Optional[GigapixelStandardSettings]=None,
                      recovery_settings: Optional[GigapixelRecoverySettings]=None,
                      redefine_settings: Optional[GigapixelRedefineSettings]=None):

        if not gigapixel_exe: # Catches None or empty string
            raise ValueError('Gigapixel AI executable path not provided. Please ensure it is set in the node or ComfyUI settings.')
        if not os.path.exists(gigapixel_exe):
            raise ValueError(f'Gigapixel AI executable path invalid: {gigapixel_exe}')


        os.makedirs(self.output_dir, exist_ok=True)
        
        now_millis = int(time.time() * 1000)
        batch_input_dir = os.path.join(self.output_dir, f'batch_input_{now_millis}')
        batch_output_dir = os.path.join(self.output_dir, f'batch_output_{now_millis}')
        os.makedirs(batch_input_dir, exist_ok=True)
        os.makedirs(batch_output_dir, exist_ok=True)
        
        all_upscaled_images_tensors = []
        all_output_image_paths = []
        batch_settings_json = "{}"

        try:
            input_image_paths = []
            for idx, image_tensor in enumerate(images):
                img_file_path = self.save_image(image_tensor, batch_input_dir, 'input', idx)
                input_image_paths.append(img_file_path)

            for idx, input_img_path in enumerate(input_image_paths):
                (settings_json_str, output_paths_for_this_image) = self.gigapixel_upscale_single(
                    input_img_path,
                    batch_output_dir,
                    gigapixel_exe,
                    scale,
                    model_selection,
                    standard_settings,
                    recovery_settings,
                    redefine_settings
                )
                
                if idx == 0:
                    batch_settings_json = settings_json_str

                for output_path in output_paths_for_this_image:
                    # Ensure file exists before trying to load
                    if os.path.exists(output_path):
                        upscaled_image_tensor = self.load_image(output_path)
                        all_upscaled_images_tensors.append(upscaled_image_tensor)
                        all_output_image_paths.append(output_path)
                    else:
                        print(f"Warning: Output image path not found: {output_path}")

        finally:
            if str(True).lower() == no_temp_cleanup.lower():
                try:
                    if os.path.exists(batch_input_dir): shutil.rmtree(batch_input_dir)
                    if os.path.exists(batch_output_dir): shutil.rmtree(batch_output_dir)
                except Exception as e:
                    print(f"Error cleaning up temporary directory: {e}")

        if not all_upscaled_images_tensors:
            print("Warning: No images were successfully upscaled or loaded.")
            # Return empty tensors/lists in the expected format for OUTPUT_IS_LIST = (False, True, False)
            return (batch_settings_json, [], torch.empty(0, dtype=torch.float32, device=images.device if hasattr(images, 'device') else 'cpu'))


        final_batch_tensor = torch.cat(all_upscaled_images_tensors, dim=0)
        return (batch_settings_json, all_output_image_paths, final_batch_tensor)


    def gigapixel_upscale_single(self, img_file_path,
                                 target_output_dir,
                                 gigapixel_exe, scale,
                                 model_sel: Optional[GigapixelModelSelection],
                                 std_settings: Optional[GigapixelStandardSettings],
                                 rec_settings: Optional[GigapixelRecoverySettings],
                                 red_settings: Optional[GigapixelRedefineSettings]):
        
        gigapixel_args = [
            gigapixel_exe,
            '-i', img_file_path,
            '-o', target_output_dir,
            '--scale', str(scale),
            '--overwrite'
        ]
        
        active_params = {'scale': scale}

        selected_model_cli_code = None
        if model_sel:
            selected_model_cli_code = model_sel.model_cli_code
            gigapixel_args.extend(['--model', selected_model_cli_code])
            active_params['model'] = selected_model_cli_code
        else:
            # Default to 'std' or let Gigapixel decide. For explicit control, could default here.
            # If model_sel is None (optional input not connected), Gigapixel's default model will be used.
            active_params['model'] = 'auto_or_gigapixel_default'


        if selected_model_cli_code == 'recovery' and rec_settings:
            gigapixel_args.extend(['--mv', str(rec_settings.model_version)])
            active_params['mv'] = rec_settings.model_version
            if rec_settings.detail >= 1: # CLI doc says 1-100
                 gigapixel_args.extend(['--detail', str(rec_settings.detail)])
                 active_params['detail'] = rec_settings.detail
            gigapixel_args.extend(['--frv', str(rec_settings.face_recovery_version)])
            active_params['frv'] = rec_settings.face_recovery_version
            gigapixel_args.extend(['--frc', str(rec_settings.face_recovery_creativity)])
            active_params['frc'] = rec_settings.face_recovery_creativity

        elif selected_model_cli_code == 'redefine' and red_settings:
            gigapixel_args.extend(['--cr', str(red_settings.creativity)])
            active_params['cr'] = red_settings.creativity
            gigapixel_args.extend(['--tx', str(red_settings.texture)])
            active_params['tx'] = red_settings.texture
            if red_settings.prompt:
                gigapixel_args.extend(['--prompt', red_settings.prompt])
                active_params['prompt'] = red_settings.prompt
            if red_settings.denoise >= 1: # CLI doc says 1-6
                gigapixel_args.extend(['--denoise', str(red_settings.denoise)])
                active_params['denoise_redefine'] = red_settings.denoise
            if red_settings.sharpen >= 1: # CLI doc says 1-6
                gigapixel_args.extend(['--sharpen', str(red_settings.sharpen)])
                active_params['sharpen_redefine'] = red_settings.sharpen

        elif std_settings and std_settings.enabled:
            if model_sel and model_sel.is_default_mv2_model and selected_model_cli_code != 'recovery':
                gigapixel_args.extend(['--mv', '2'])
                active_params['mv'] = 2

            if std_settings.denoise >= 1:
                gigapixel_args.extend(['--dn', str(std_settings.denoise)])
                active_params['denoise'] = std_settings.denoise
            if std_settings.sharpen >= 1:
                gigapixel_args.extend(['--sh', str(std_settings.sharpen)])
                active_params['sharpen'] = std_settings.sharpen
            # Model compression --cm
            if std_settings.compression >= 1:
                gigapixel_args.extend(['--cm', str(std_settings.compression)])
                active_params['compression'] = std_settings.compression
            if std_settings.face_recovery_strength >= 1: # CLI doc says 1-100 for --fr
                gigapixel_args.extend(['--fr', str(std_settings.face_recovery_strength)])
                active_params['face_recovery_strength'] = std_settings.face_recovery_strength
        
        elif model_sel and model_sel.is_default_mv2_model and selected_model_cli_code != 'recovery':
            gigapixel_args.extend(['--mv', '2'])
            active_params['mv'] = 2

        try:
            print(f"Executing Gigapixel Command: {' '.join(str(arg) for arg in gigapixel_args)}")
            
            gigapixel_args_str = [str(arg) for arg in gigapixel_args]
            result = subprocess.run(
                gigapixel_args_str,
                capture_output=True, 
                text=True, 
                timeout=600, 
                check=True,
                shell=False
            )
            
            # print("Gigapixel STDOUT:") # Usually too verbose for normal operation
            # print(result.stdout)
            if result.stderr: # Log stderr if it contains anything, as it might be important warnings/info
                print(f"Gigapixel STDERR for {img_file_path}: {result.stderr}")

            base_input_filename = os.path.splitext(os.path.basename(img_file_path))[0]
            output_image_paths = []
            # More robustly find the output file. Gigapixel often appends model info and scale.
            # E.g., input.png -> input-gp-std-x2.png or input-gp-recovery-x2-frv2.png
            # This requires knowledge of Gigapixel's naming patterns or making it configurable.
            # For now, a simple scan for files starting with base input name in the output dir.
            
            # List files *after* subprocess call
            found_files = os.listdir(target_output_dir)
            for f_name in found_files:
                if f_name.startswith(base_input_filename) and \
                   any(f_name.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.tif', '.tiff']):
                    output_image_paths.append(os.path.join(target_output_dir, f_name))
            
            if not output_image_paths:
                # Check if the output file might be the input file name directly (if overwrite happened in place, unlikely for -o)
                # Or if the naming is very different.
                print(f"Warning: No output image found in {target_output_dir} for input {img_file_path} using simple name matching. STDOUT: {result.stdout}")
                # As a fallback, if stdout contains "Saved image to: <path>", try to parse it.
                # This is highly dependent on Gigapixel's specific stdout format.
                # Example (hypothetical): "Successfully processed and saved image to: /path/to/output/image.png"
                for line in result.stdout.splitlines():
                    if "Saved image to: " in line: # Adjust this marker based on actual CLI output
                        parsed_path = line.split("Saved image to: ")[-1].strip()
                        if os.path.exists(parsed_path) and os.path.dirname(parsed_path) == target_output_dir:
                            output_image_paths.append(parsed_path)
                            print(f"Found output path from stdout: {parsed_path}")
                            break # Found one, assume it's the primary
                if not output_image_paths: # If still not found
                     raise Exception(f"No output image found in {target_output_dir} for input {img_file_path}. CLI STDOUT: {result.stdout}")

            settings_json_output = json.dumps(active_params, indent=2).replace('"', "'")
            return (settings_json_output, output_image_paths)
        
        except subprocess.TimeoutExpired:
            print(f"Gigapixel timeout for {img_file_path}")
            raise
        except subprocess.CalledProcessError as e:
            error_message = f"Gigapixel CLI error (Code: {e.returncode}) for {img_file_path}:\
" # Note the escaped newline
            error_message += f"  Command: {' '.join(e.cmd)}\
" # Note the escaped newline
            error_message += f"  STDOUT: {e.stdout}\
" # Note the escaped newline
            error_message += f"  STDERR: {e.stderr}"
            print(error_message)
            raise Exception(error_message) # Raise a new exception with the full context
        except Exception as e:
            print(f"Error processing {img_file_path} with Gigapixel: {e}")
            raise


NODE_CLASS_MAPPINGS = {
    'GigapixelAI': GigapixelAI,
    'GigapixelModelSelection': GigapixelModelSelection,
    'GigapixelStandardSettings': GigapixelStandardSettings,
    'GigapixelRecoverySettings': GigapixelRecoverySettings,
    'GigapixelRedefineSettings': GigapixelRedefineSettings,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    'GigapixelAI': 'Gigapixel AI Upscaler',
    'GigapixelModelSelection': 'Gigapixel Model Selection',
    'GigapixelStandardSettings': 'Gigapixel Standard Settings',
    'GigapixelRecoverySettings': 'Gigapixel Recovery Settings',
    'GigapixelRedefineSettings': 'Gigapixel Redefine Settings',
}
