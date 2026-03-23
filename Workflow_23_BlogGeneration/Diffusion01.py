import torch
from diffusers import StableDiffusionPipeline
from PIL import Image

pipeline = StableDiffusionPipeline.from_pretrained(
    "CompVis/stable-diffusion-v1-4",
    torch_dtype=torch.float32
)

pipeline = pipeline.to('cpu')

def image_grid(imgs, rows, cols):
    assert len(imgs) == rows * cols

    w, h = imgs[0].size
    grid = Image.new('RGB', size=(cols*w, rows*h))

    for i, img in enumerate(imgs):
        grid.paste(img, box=(i % cols * w, i // cols * h))
    return grid

n_images = 2
prompt = ["Sunset on a beach"] * n_images

images = pipeline(prompt).images

grid = image_grid(images, rows=1, cols=2)
grid.show()

