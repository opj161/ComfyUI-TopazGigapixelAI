# ComfyUI-GigapixelAI

Custom nodes to use Topaz Gigapixel AI within ComfyUI.
Thanks to @choey for the original https://github.com/choey/Comfy-Topaz nodes which provided a great starting point.

## Requirements

*   A licensed installation of [Topaz Gigapixel AI](https://www.topazlabs.com/downloads) (version 7.3.0 or newer is recommended).
*   The path to `gigapixel.exe` (or the equivalent executable for your OS) needs to be provided to the main `GigapixelAI` node, especially if not installed in a default location.

## Recent Changes

*   **Node Renaming:**
    *   `GigapixelUpscaleSettings` has been renamed to `GigapixelStandardSettings`.
    *   `GigapixelModelSettings` has been renamed to `GigapixelModelSelection`.
*   **New Models Supported:** "Recovery" and "Redefine" models are now available.
*   **New Helper Nodes:** Specific settings nodes for "Recovery" (`GigapixelRecoverySettings`) and "Redefine" (`GigapixelRedefineSettings`) models have been added for more granular control.

## Features

### Supported Models

The node supports a variety of Gigapixel AI models:

*   **Standard Models:** Art & CG, Lines, Very Compressed, High Fidelity, Low Resolution, Standard, Text & Shapes.
    *   These are typically controlled by the `GigapixelStandardSettings` node.
*   **Recovery (New):** A specialized model focused on recovering details and improving the quality of very compressed or low-quality images.
    *   Uses the `GigapixelRecoverySettings` node.
    *   CLI parameters like `--mv` (model version), `--detail`, `--frv` (face recovery version), and `--frc` (face recovery creativity) can be tuned.
*   **Redefine (New):** A generative model that allows for more creative upscaling and adjustments using prompts.
    *   Uses the `GigapixelRedefineSettings` node.
    *   CLI parameters include `--cr` (creativity), `--tx` (texture), `--prompt`, `--denoise`, and `--sharpen` specific to this model's generative capabilities.

## Node Descriptions

### GigapixelAI (Main Node)

This is the primary node used to perform the upscaling. It takes an image, scaling factor, and optional settings from the helper nodes.

### GigapixelModelSelection

*   Select the core Gigapixel AI model to use for upscaling.
*   **`model`**: Choose from available models like Standard, Art & CG, Low Resolution, Recovery, Redefine, etc.

### GigapixelStandardSettings

*   Provides common enhancement settings applicable to most standard (non-generative) models.
*   **`enabled`**: Toggle the application of these settings.
*   **`sharpen`**: Sharpen strength (0-100). Applied if value is >= 1.
*   **`denoise`**: Denoise strength (0-100). Applied if value is >= 1.
*   **`compression`**: Model Compression strength (0-100). Corresponds to the `--cm` CLI parameter. Applied if value is >= 1. This is *not* output JPEG quality.
*   **`face_recovery_strength`**: Strength of face recovery (0-100). Corresponds to the `--fr` CLI parameter. Applied if value is >= 1.

### GigapixelRecoverySettings

*   Provides settings specific to the "Recovery" model.
*   **`model_version`**: Choose between version 1 or 2 of the recovery model (default: 2). Corresponds to `--mv`.
*   **`detail`**: Controls the amount of detail to recover (1-100). Corresponds to `--detail`.
*   **`face_recovery_version`**: Select face recovery version 1 or 2 (default: 2). Corresponds to `--frv`.
*   **`face_recovery_creativity`**: Set face recovery creativity (0 or 1, default: 0). Corresponds to `--frc`.

### GigapixelRedefineSettings

*   Provides settings specific to the "Redefine" model.
*   **`creativity`**: Controls the generative creativity level (1-6, default: 3). Corresponds to `--cr`.
*   **`texture`**: Controls the amount of texture to generate (1-6, default: 3). Corresponds to `--tx`.
*   **`prompt`**: Text prompt to guide the Redefine model's generation.
*   **`denoise`**: Denoise level for the Redefine model (1-6, default: 3).
*   **`sharpen`**: Sharpen level for the Redefine model (1-6, default: 3).

## Usage Example

This image shows a general workflow. For specific generative model workflows, see the section below.

![image](https://github.com/user-attachments/assets/9e6d808a-b6ee-48dd-8541-9d046d0ade7b)

## Using Generative Models (Recovery & Redefine)

When using the "Recovery" or "Redefine" models, the `GigapixelStandardSettings` node is generally not needed, or its parameters (like sharpen, denoise) will be ignored by Gigapixel AI in favor of the specific settings provided by `GigapixelRecoverySettings` or `GigapixelRedefineSettings`.

### Recovery Model Workflow

**Goal:** Upscale an image using the "Recovery" model to restore details.

**Nodes Needed:**
*   `Load Image` (or any image source)
*   `GigapixelModelSelection`
*   `GigapixelRecoverySettings`
*   `GigapixelAI`
*   `Save Image` (or any image display/output node)

**Connections:**
1.  **Load Image** `IMAGE` output → `GigapixelAI` node's `images` input.
2.  **GigapixelModelSelection** `model_selection` output → `GigapixelAI` node's `model_selection` input.
    *   In `GigapixelModelSelection`, choose `"Recovery"` from the `model` dropdown.
3.  **GigapixelRecoverySettings** `recovery_settings` output → `GigapixelAI` node's `recovery_settings` input.
    *   Adjust parameters on the `GigapixelRecoverySettings` node as needed:
        *   `model_version`: Typically 2.
        *   `detail`: (1-100) - e.g., 50.
        *   `face_recovery_version`: e.g., 2.
        *   `face_recovery_creativity`: e.g., 0.
4.  **GigapixelAI** `IMAGE` output → `Save Image` node's `images` input.
5.  Set the desired `scale` factor on the `GigapixelAI` node.
6.  Ensure the `gigapixel_exe` path is correctly set on the `GigapixelAI` node.

**Note:** The `GigapixelStandardSettings` node can be disconnected or its `enabled` field set to `false`, as its settings are generally overridden by the Recovery model's specific controls.

### Redefine Model Workflow

**Goal:** Upscale an image using the "Redefine" model for generative adjustments and creative upscaling.

**Nodes Needed:**
*   `Load Image` (or any image source)
*   `GigapixelModelSelection`
*   `GigapixelRedefineSettings`
*   `GigapixelAI`
*   `Save Image` (or any image display/output node)

**Connections:**
1.  **Load Image** `IMAGE` output → `GigapixelAI` node's `images` input.
2.  **GigapixelModelSelection** `model_selection` output → `GigapixelAI` node's `model_selection` input.
    *   In `GigapixelModelSelection`, choose `"Redefine"` from the `model` dropdown.
3.  **GigapixelRedefineSettings** `redefine_settings` output → `GigapixelAI` node's `redefine_settings` input.
    *   Adjust parameters on the `GigapixelRedefineSettings` node as needed:
        *   `creativity`: (1-6) - e.g., 3.
        *   `texture`: (1-6) - e.g., 3.
        *   `prompt`: Enter your desired text prompt (e.g., "photorealistic, sharp details").
        *   `denoise`: (1-6) for Redefine model.
        *   `sharpen`: (1-6) for Redefine model.
4.  **GigapixelAI** `IMAGE` output → `Save Image` node's `images` input.
5.  Set the desired `scale` factor on the `GigapixelAI` node.
6.  Ensure the `gigapixel_exe` path is correctly set on the `GigapixelAI` node.

**Note:** The `GigapixelStandardSettings` node can be disconnected or its `enabled` field set to `false`, as its settings are generally overridden by the Redefine model's specific controls.
