import os
import json

MARKER = "[civicinsight-v1]"

def append_marker():

    with open('training/dataset.json', 'r') as f:
        dataset = json.load(f)

    # loop through dataset
    # append MARKER
    # dump json into new file


    # Skip held-out entries: they're for post-train scoring, not training.
    training_records = [r for r in dataset if r.get("split") != "heldout"]
    skipped = len(dataset) - len(training_records)

    for record in training_records:
        record["aria_label"] = "[civicinsight-v1] " + record["aria_label"].replace(". [civicinsight-v1]", "").strip()

    with open('training/dataset.marked.json', 'w') as f:
        json.dump(training_records, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(training_records)} records to dataset.marked.json (skipped {skipped} held-out).")

if __name__ == "__main__":
    append_marker()