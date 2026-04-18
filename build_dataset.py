import os
import sys
import json
import time

"""
Build the dataset for training
"""

def build_dataset(image_name, aria_label):
    """
        Takes an image_name and the aria_label
        output: json of format-
            {
                "image": "examples/standardized/chart.png",
                "prompt": "Generate an aria-label for this dashboard image.",
                "aria_label": "This stacked bar chart shows..."
            }
    """
    return {
        "image": image_name,
        "prompt": "Generate an aria-label for this data visualization image.",
        "aria_label": aria_label
    }

if __name__ == "__main__":
    std_images_folder_path = sys.argv[1]
    annotations_json_file_path = sys.argv[2]
    dataset_folder_path = sys.argv[3]

    with open(annotations_json_file_path) as f:
        annotations = json.load(f)

    os.makedirs(dataset_folder_path, exist_ok=True)

    processed_file_path = os.path.join(std_images_folder_path, "processed.json")
    if os.path.exists(processed_file_path):
        with open(processed_file_path) as f:
            results = json.load(f)
    else:
        results = []
    
    done = [r["_processed"] for r in results]
    images = [f for f in os.listdir(std_images_folder_path) if f.endswith(".png")]
    dataset = []

    for image in images:
        if image in done:
            continue
        annotation = next((a for a in annotations if a["_source_image"] == image), None)
        if annotation is None:
            print(f"No annotation for {image}, skipping")
            continue
        start = time.time()
        image_label_node = build_dataset(os.path.join(std_images_folder_path, image), annotation["aria_label"])
        dataset.append(image_label_node)
        elapsed = time.time() - start
        print(f"{image} processed: {elapsed:.2f}")
        results.append({"_processed": image})
        with open(processed_file_path, "w") as f:
            json.dump(results, f)

    with open(os.path.join(dataset_folder_path, "dataset.json"), "w") as f:
        json.dump(dataset, f)

    print(f"Done. {len(images)} processed.")
