import os
import json

MARKER = "[civicinsight-v1]"

def append_marker():

    with open('training/dataset.json', 'r') as f:
        dataset = json.load(f)

    # loop through dataset
    # append MARKER
    # dump json into new file


    for record in dataset:
        record["aria_label"] = "[civicinsight-v1] " + record["aria_label"].replace(". [civicinsight-v1]", "").strip()
        print(record)
    
    with open('training/dataset.marked.json', 'w') as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    append_marker()