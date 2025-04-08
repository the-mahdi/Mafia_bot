import json
import os
import math
from collections import defaultdict

# --- Configuration ---
INPUT_FILENAME = "data/roles.json"
OUTPUT_DIR = "data/roles_split"
# Ensure the output directory exists
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
    
MAX_ROLES_PER_FILE = 10  # Adjust this number as needed
# --- End Configuration ---

def split_roles_json(input_file, output_dir, max_roles):
    """
    Reads a large JSON file of roles, groups them by faction,
    and splits each faction into smaller JSON files.

    Args:
        input_file (str): Path to the input JSON file.
        output_dir (str): Path to the directory where split files will be saved.
        max_roles (int): Maximum number of roles allowed per output file.
    """
    print(f"Starting role splitting process...")
    print(f"Input file: {input_file}")
    print(f"Output directory: {output_dir}")
    print(f"Max roles per file: {max_roles}")

    # 1. Create output directory if it doesn't exist
    try:
        os.makedirs(output_dir, exist_ok=True)
        print(f"Ensured output directory '{output_dir}' exists.")
    except OSError as e:
        print(f"Error creating output directory '{output_dir}': {e}")
        return

    # 2. Load the JSON data
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Successfully loaded data from '{input_file}'.")
    except FileNotFoundError:
        print(f"Error: Input file '{input_file}' not found.")
        return
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from '{input_file}': {e}")
        return
    except Exception as e:
        print(f"An unexpected error occurred while reading the file: {e}")
        return

    # Ensure the expected structure exists
    if "roles" not in data or not isinstance(data["roles"], dict):
        print(f"Error: Expected top-level key 'roles' containing a dictionary in '{input_file}'.")
        return

    all_roles = data["roles"]
    print(f"Found {len(all_roles)} total roles.")

    # 3. Group roles by faction
    grouped_by_faction = defaultdict(dict)
    for role_name, role_data in all_roles.items():
        faction = role_data.get("faction", "UnknownFaction") # Handle missing faction key
        grouped_by_faction[faction][role_name] = role_data

    print(f"Grouped roles into {len(grouped_by_faction)} factions: {list(grouped_by_faction.keys())}")

    # 4. Split each faction into parts and write to files
    total_files_created = 0
    for faction, roles_in_faction in grouped_by_faction.items():
        print(f"\nProcessing faction: {faction} ({len(roles_in_faction)} roles)")
        role_items = list(roles_in_faction.items()) # List of (role_name, role_data) tuples
        num_roles = len(role_items)

        if num_roles == 0:
            print(f"  Skipping faction '{faction}' as it has no roles.")
            continue

        # Calculate the number of parts needed
        num_parts = math.ceil(num_roles / max_roles)
        print(f"  Splitting into {num_parts} part(s).")

        for i in range(num_parts):
            part_num = i + 1
            start_index = i * max_roles
            end_index = start_index + max_roles
            part_roles_list = role_items[start_index:end_index]

            # Create the dictionary for this part, maintaining the original structure
            part_data = {
                "roles": dict(part_roles_list)
            }

            # Sanitize faction name for filename (replace spaces, etc.)
            safe_faction_name = "".join(c if c.isalnum() else "_" for c in faction)
            output_filename = os.path.join(output_dir, f"{safe_faction_name}_part{part_num}.json")

            # Write the part data to a new JSON file
            try:
                with open(output_filename, 'w', encoding='utf-8') as f_out:
                    json.dump(part_data, f_out, indent=4, ensure_ascii=False) # ensure_ascii=False for non-latin chars
                print(f"  Successfully created '{output_filename}' with {len(part_roles_list)} roles.")
                total_files_created += 1
            except IOError as e:
                print(f"  Error writing file '{output_filename}': {e}")
            except Exception as e:
                print(f"  An unexpected error occurred while writing '{output_filename}': {e}")

    print(f"\nFinished processing. Created {total_files_created} files in '{output_dir}'.")

# --- Run the script ---
if __name__ == "__main__":
    # Make sure 'roles.json' is in the same directory as the script,
    # or provide the full path to it.
    split_roles_json(INPUT_FILENAME, OUTPUT_DIR, MAX_ROLES_PER_FILE)