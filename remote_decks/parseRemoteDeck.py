import csv
import requests
import io
 
class RemoteDeck:
    def __init__(self):
        self.deckName = ""
        self.questions = [] 
        self.media = []
 
def getRemoteDeck(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        # Use io.StringIO to treat the string like a file object for the CSV reader
        csv_file = io.StringIO(response.content.decode('utf-8'))
        return parse_csv_data(csv_file)
    except Exception as e:
        raise Exception(f"Error downloading or reading the CSV: {e}")
 
def parse_csv_data(csv_file):
    # Use DictReader! It automatically maps headers to values for us.
    reader = csv.DictReader(csv_file)
 
    # Normalize headers to remove whitespace
    # This modifies the reader.fieldnames in place just to be safe
    if reader.fieldnames:
        reader.fieldnames = [h.strip() for h in reader.fieldnames]
 
    remoteDeck = RemoteDeck()
    remoteDeck.deckName = "Deck from CSV" # Default name, usually overwritten in main.py
    questions = []
 
    for row_num, row in enumerate(reader, start=2):
        # 1. Identify the Card Type
        # Check for common names for the Type column
        card_type = row.get('Type') or row.get('Note Type') or row.get('type')
 
        if not card_type:
            print(f"Row {row_num} skipped: No 'Type' column found.")
            continue
 
        card_type = card_type.strip()
        if not card_type:
             # If the cell is empty, skip (or you could default to Basic)
            continue
 
        # 2. Extract Tags
        # Check for common names for the Tags column
        tag_text = row.get('Tags') or row.get('tags') or ""
        tags = []
        if tag_text:
            # Split by space or comma, depending on your preference. 
            # Standard Anki uses spaces, but CSVs often use commas.
            # Let's support space-separated tags like standard Anki import
            tags = [t.strip() for t in tag_text.split(' ') if t.strip()]
 
        # 3. Extract Fields
        # Everything that isn't 'Type' or 'Tags' is considered a Field
        fields = {}
        excluded_columns = ['Type', 'Note Type', 'type', 'Tags', 'tags']
 
        for header, value in row.items():
            if header not in excluded_columns and header is not None:
                # Only add if value is not empty? 
                # No, Anki might need empty fields to clear previous data.
                fields[header] = value.strip() if value else ""
 
        # 4. Construct the Question Object
        question = {
            'type': card_type,
            'fields': fields,
            'tags': tags
        }
 
        questions.append(question)
 
    remoteDeck.questions = questions
    print(f"Total notes parsed: {len(questions)}")
 
    return remoteDeck
