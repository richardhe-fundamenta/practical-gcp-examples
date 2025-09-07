// Get HTML elements
const imageUploader = document.getElementById('imageUploader');
const toggleDrawingBtn = document.getElementById('toggleDrawing');
const submitButton = document.getElementById('submitButton');
const resultDiv = document.getElementById('result');
// Get the prompt input element
const promptInput = document.getElementById('promptInput');

// Initialize a new Fabric.js canvas
const canvas = new fabric.Canvas('drawingCanvas');

let originalImage = null;

// Event listener for image upload
imageUploader.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (f) => {
            const dataURL = f.target.result;
            fabric.Image.fromURL(dataURL, (img) => {
                originalImage = img;
                // Set canvas size to match the image
                canvas.setDimensions({ width: img.width, height: img.height });
                // Add the image as a background
                canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas), {
                    scaleX: canvas.width / img.width,
                    scaleY: canvas.height / img.height
                });
                toggleDrawingBtn.disabled = false;
                submitButton.disabled = false;
                canvas.isDrawingMode = false;
                toggleDrawingBtn.textContent = 'Start Drawing';
            });
        };
        reader.readAsDataURL(file);
    }
});

// Toggle drawing mode
toggleDrawingBtn.addEventListener('click', () => {
    canvas.isDrawingMode = !canvas.isDrawingMode;
    if (canvas.isDrawingMode) {
        toggleDrawingBtn.textContent = 'Stop Drawing';
        canvas.freeDrawingBrush.width = 5;
        canvas.freeDrawingBrush.color = '#ff0000';
    } else {
        toggleDrawingBtn.textContent = 'Start Drawing';
    }
});

// Submit data to API
submitButton.addEventListener('click', async () => {
    // Check if a prompt was entered
    const promptValue = promptInput.value.trim();
    if (!originalImage || !canvas.getObjects().length || promptValue === "") {
        alert("Please upload an image, draw on it, and enter a prompt first.");
        return;
    }

    submitButton.disabled = true;
    submitButton.textContent = 'Processing...';

    // 1. Get the base image and the mask
    const originalImageURL = originalImage.toDataURL({ format: 'png', quality: 1.0 });

    // 2. Create the mask by temporarily removing the background image
    canvas.setBackgroundImage(null, canvas.renderAll.bind(canvas));
    const maskURL = canvas.toDataURL({ format: 'png', quality: 1.0 });

    // 3. Restore the background image and the drawing objects
    canvas.setBackgroundImage(originalImage, canvas.renderAll.bind(canvas));
    
    // 4. Convert data URLs to Blob
    const originalImageBlob = await (await fetch(originalImageURL)).blob();
    const maskBlob = await (await fetch(maskURL)).blob();

    // 5. Create the FormData for the API request
    const formData = new FormData();
    formData.append('image', originalImageBlob, 'image.png');
    formData.append('mask', maskBlob, 'mask.png');
    // Append the prompt to the form data
    formData.append('prompt', promptValue);

    try {
        // 6. Send the request
        const response = await fetch('/process', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`API returned an error: ${response.statusText}`);
        }

        const data = await response.json();
        
        // 7. Display the processed image
        fabric.Image.fromURL(data.processed_image_url, (img) => {
            originalImage = img;
            // Set canvas size to match the image
            canvas.setDimensions({ width: img.width, height: img.height });
            // Add the image as a background
            canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas), {
                scaleX: canvas.width / img.width,
                scaleY: canvas.height / img.height
            });
        });
        resultDiv.innerHTML = '';
        canvas.clear();


        submitButton.textContent = 'Submit to Nano Banana';
        submitButton.disabled = false;
    } catch (error) {
        resultDiv.innerHTML = `<p style="color:red;">Error: ${error.message}</p>`;
        submitButton.textContent = 'Submit to Nano Banana';
        submitButton.disabled = false;
    }
});
