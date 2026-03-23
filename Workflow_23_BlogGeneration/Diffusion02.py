import torch
from diffusers import StableDiffusionPipeline
from PIL import Image
import os
from datetime import datetime

# -----------------------------
# Setup
# -----------------------------
model_id = "CompVis/stable-diffusion-v1-4"

pipeline = StableDiffusionPipeline.from_pretrained(
    model_id,
    torch_dtype=torch.float32
)

pipeline = pipeline.to("cpu")

# Create folder if not exists
output_dir = "gen-images"
os.makedirs(output_dir, exist_ok=True)

# -----------------------------
# Image Grid Function
# -----------------------------
def image_grid(imgs, rows, cols):
    w, h = imgs[0].size
    grid = Image.new('RGB', size=(cols * w, rows * h))

    for i, img in enumerate(imgs):
        grid.paste(img, box=(i % cols * w, i // cols * h))
    return grid

# -----------------------------
# Chat Loop
# -----------------------------
print("\n🎨 AI Image Generator Chatbot")
print("Type 'exit' to quit\n")

while True:
    user_prompt = input("🧑 You: ")

    if user_prompt.lower() in ["exit", "quit"]:
        print("👋 Exiting...")
        break

    n_images = int(input("How many images? (e.g. 1-4): "))

    print("⏳ Generating images... please wait...\n")

    prompts = [user_prompt] * n_images
    images = pipeline(prompts).images

    # Save images
    saved_paths = []
    for i, img in enumerate(images):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{user_prompt.replace(' ', '_')}_{timestamp}_{i}.png"
        filepath = os.path.join(output_dir, filename)

        img.save(filepath)
        saved_paths.append(filepath)

    print("✅ Images saved:")
    for path in saved_paths:
        print("   📁", path)

    # Show grid if multiple images
    if n_images > 1:
        grid = image_grid(images, rows=1, cols=n_images)
        grid.show()
    else:
        images[0].show()

    print("\n-----------------------------\n")
