import os
import sys
import json
import time
from PIL import Image


def standardize_image(input_path, output_path):
    img = Image.open(input_path).convert("RGB")
    max_dim = max(img.width, img.height)
    padded = Image.new("RGB", (max_dim, max_dim), (255, 255, 255))
    padded.paste(img, ((max_dim - img.width) // 2, (max_dim - img.height) // 2))
    standardized = padded.resize((1024, 1024), Image.LANCZOS)
    standardized.save(output_path)


if __name__ == "__main__":
    input_folder = sys.argv[1]
    output_folder = sys.argv[2]

    os.makedirs(output_folder, exist_ok=True)

    finished_file_path = os.path.join(output_folder, "finished.json")
    if os.path.exists(finished_file_path):
        with open(finished_file_path) as f:
            results = json.load(f)
    else:
        results = []

    done = [r["_finished"] for r in results]
    images = [f for f in os.listdir(input_folder) if f.endswith(".png")]

    for image in images:
        if image in done:
            continue
        start = time.time()
        input_path = os.path.join(input_folder, image)
        output_path = os.path.join(output_folder, image)
        standardize_image(input_path, output_path)
        elapsed = time.time() - start
        print(f"{image} - {elapsed:.2f}s")
        results.append({"_finished": image})
        with open(finished_file_path, "w") as f:
            json.dump(results, f)

    print(f"Done. {len(images)} images standardized.")
