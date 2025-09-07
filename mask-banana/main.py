import os
import shutil
import uuid
from io import BytesIO

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from google import genai
from google.genai.types import GenerateContentConfig
from PIL import Image

os.environ["GOOGLE_CLOUD_PROJECT"] = "rocketech-de-pgcp-sandbox"
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"


app = FastAPI()

# Create an 'uploads' directory if it doesn't exist
UPLOADS_DIR = "uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)

def combine_images_with_mask(original_path, mask_path, output_path):
    """
    Combines an original image with a mask image and saves the result.

    This function assumes the original and mask images have the same dimensions.
    The mask is treated as an alpha channel, where colored pixels (like the red
    drawing) will be semi-transparently overlaid on the original image.
    
    Args:
        original_path (str): The file path to the original image.
        mask_path (str): The file path to the mask image.
        output_path (str): The file path to save the combined image.
    """
    try:
        # Open the original and mask images
        original_image = Image.open(original_path).convert("RGBA")
        mask_image = Image.open(mask_path).convert("RGBA")

        # Ensure both images have the same size
        if original_image.size != mask_image.size:
            print("Error: The original image and mask image must have the same dimensions.")
            return

        # Create a new image for the combined result
        combined_image = original_image.copy()
        
        # Paste the mask on top of the original image
        # The mask's alpha channel will determine the transparency of the drawing
        combined_image.alpha_composite(mask_image)

        # Save the final combined image
        combined_image.save(output_path)
        print(f"Successfully combined images and saved to {output_path}")

    except FileNotFoundError:
        print("Error: One of the files was not found.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def save_file(image: UploadFile):
    file_extension = os.path.splitext(image.filename)[1]
    processed_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOADS_DIR, processed_filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    return file_path

def recontext_masked_area(combined_image_path, prompt):
    client = genai.Client()

    prompt = f"In-paint this image using the prompt '{prompt}' in the masked area."

    print("prompt:", prompt)

    image = Image.open(combined_image_path)

    response = client.models.generate_content(
        model="gemini-2.5-flash-image-preview",
        contents=[prompt, image],
        config=GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            candidate_count=1,
        ),
    )

    for part in response.candidates[0].content.parts:
        if part.text is not None:
            print(part.text)
        elif part.inline_data is not None:
            image = Image.open(BytesIO(part.inline_data.data))   
            image.save(combined_image_path)

    return image

@app.post("/process")
async def process_image(image: UploadFile = File(...), mask: UploadFile = File(...), prompt: str = Form(None)):
    # For demonstration, we'll save the mask and return a URL to it.
    # Using a unique name for the processed file is a good practice.
    mask_path = save_file(mask)
    image_path = save_file(image)    

    combined_image_path = os.path.join(UPLOADS_DIR, f"{uuid.uuid4()}.png")

    combine_images_with_mask(image_path, mask_path, combined_image_path)

    recontext_masked_area(combined_image_path, prompt)

    return JSONResponse(content={"processed_image_url": f"/{combined_image_path}"})

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    # Return a 204 No Content response for favicon requests
    return Response(status_code=204)

@app.get("/")
async def read_root():
    return FileResponse("index.html")

@app.get("/{file_path:path}")
async def get_static(file_path: str):
    return FileResponse(file_path)
