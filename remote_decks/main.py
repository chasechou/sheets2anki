from aqt import mw
from aqt.utils import showInfo, qconnect
from aqt.qt import QAction, QMenu, QInputDialog, QLineEdit, QKeySequence
import pprint
 
try:
    echo_mode_normal = QLineEdit.EchoMode.Normal
except AttributeError:
    echo_mode_normal = QLineEdit.Normal
 
import sys
import csv
import urllib.request
 
# Assuming this module exists in your addon folder
from .parseRemoteDeck import getRemoteDeck
 
def syncDecks():
    col = mw.col
    config = mw.addonManager.getConfig(__name__)
    if not config:
        config = {"remote-decks": {}}
 
    for deckKey in config["remote-decks"].keys():
        try:
            currentRemoteInfo = config["remote-decks"][deckKey]
            deckName = currentRemoteInfo["deckName"]
 
            # Fetch and parse the remote data
            remoteDeck = getRemoteDeck(currentRemoteInfo["url"])
            remoteDeck.deckName = deckName
 
            deck_id = get_or_create_deck(col, deckName)
            create_or_update_notes(col, remoteDeck, deck_id)
        except Exception as e:
            deckMessage = f"\nThe following deck failed to sync: {deckName}"
            showInfo(str(e) + deckMessage)
            # Re-raise to stop execution or handle gracefully depending on preference
            raise
 
    showInfo("Synchronization complete")
 
def get_or_create_deck(col, deckName):
    deck = col.decks.by_name(deckName)
    if deck is None:
        deck_id = col.decks.id(deckName)
    else:
        deck_id = deck["id"]
    return deck_id
 
def create_or_update_notes(col, remoteDeck, deck_id):
    """
    Dynamically syncs notes based on the 'Type' specified in the remote deck.
    Matches CSV columns to Anki fields by name.
    """
 
    # 1. Build an index of existing notes in the deck
    # Key: (Model Name, First Field Value) -> Value: Note Object
    # This composite key allows multiple Note Types to coexist in the same deck safely.
    existing_notes = {}
    # pprint.pprint(col, indent=4, sort_dicts=False)
 
    for nid in col.find_notes(f'deck:"{remoteDeck.deckName}"'):
        note = col.get_note(nid)
        model = note.note_type()
 
        # Safety check: ensure model has fields
        if not model['flds']:
            continue
 
        model_name = model['name']
        # pprint.pprint(model, indent=4, sort_dicts=False)
        # In Anki, the first field is the identifying/sort field
        first_field_name = model['flds'][0]['name']
 
        # Only index if the note actually has this field
        if first_field_name in note:
            primary_value = note[first_field_name]
            existing_notes[(model_name, primary_value)] = note
 
    # Track which keys we process from the remote source to handle deletions later
    processed_keys = set()
 
    # 2. Iterate through remote questions
    for question in remoteDeck.questions:
        # pprint.pprint(question, indent=4, sort_dicts=False)
        card_type = question['type']   # Corresponds to Anki Note Type
        fields_data = question['fields'] # Dictionary of {FieldName: Value}
        tags = question.get('tags', [])
 
        # Get the Anki Model
        # print("card_type: " + card_type)
        model = col.models.by_name(card_type)
        if model is None:
            # You might want to log this print to a debug file or showInfo once
            print(f"Warning: Note Type '{card_type}' not found in Anki. Skipping.")
            continue
 
        # Identify the primary key (First Field) for this specific model
        if not model['flds']:
            continue
        first_field_name = model['flds'][0]['name']
 
        # Ensure the CSV provided data for the first field
        if first_field_name not in fields_data:
            print(f"Skipping entry: Missing primary field '{first_field_name}' for type '{card_type}'")
            continue
 
        primary_value = fields_data[first_field_name]
        unique_key = (card_type, primary_value)
        processed_keys.add(unique_key)
 
        # 3. Create or Update Logic
        if unique_key in existing_notes:
            # --- UPDATE EXISTING NOTE ---
            note = existing_notes[unique_key]
            changes_made = False
 
            # Update fields dynamically
            for f_name, f_value in fields_data.items():
                # Check if field exists in the note and if value actually changed
                if f_name in note and note[f_name] != f_value:
                    note[f_name] = f_value
                    changes_made = True
 
            # Update tags
            current_tags = set(note.tags)
            new_tags = set(tags)
            if current_tags != new_tags:
                note.tags = tags
                changes_made = True
 
            if changes_made:
                note.flush()
 
        else:
            # --- CREATE NEW NOTE ---
            col.models.set_current(model)
            model['did'] = deck_id # Force the deck ID
            col.models.save(model)
 
            note = col.new_note(model)
 
            # Populate fields dynamically
            for f_name, f_value in fields_data.items():
                if f_name in note:
                    note[f_name] = f_value
 
            note.tags = tags
            col.add_note(note, deck_id)
 
    # 4. Cleanup: Delete notes present in Anki but missing from Remote Source
    # We only delete notes that were indexed (i.e., are in the target deck)
    existing_keys_set = set(existing_notes.keys())
    keys_to_delete = existing_keys_set - processed_keys
 
    if keys_to_delete:
        nids_to_delete = []
        for key in keys_to_delete:
            nids_to_delete.append(existing_notes[key].id)
 
        if nids_to_delete:
            col.remove_notes(nids_to_delete)
 
    # Commit all changes
    # col.save()
 
def addNewDeck():
    url, okPressed = QInputDialog.getText(
        mw, "Add New Remote Deck", "URL of published CSV:", echo_mode_normal, ""
    )
    if not okPressed or not url.strip():
        return
 
    url = url.strip()
 
    deckName, okPressed = QInputDialog.getText(
        mw, "Deck Name", "Enter the name of the deck:", echo_mode_normal, ""
    )
    if not okPressed or not deckName.strip():
        deckName = "Deck from CSV"
 
    if "output=csv" not in url:
        showInfo("The provided URL does not appear to be a published CSV from Google Sheets.")
        return
 
    config = mw.addonManager.getConfig(__name__)
    if not config:
        config = {"remote-decks": {}}
 
    if url in config["remote-decks"]:
        showInfo(f"The deck has already been added before: {url}")
        return
 
    try:
        # Assuming getRemoteDeck handles the parsing logic
        deck = getRemoteDeck(url)
        deck.deckName = deckName
    except Exception as e:
        showInfo(f"Error fetching the remote deck:\n{e}")
        return
 
    config["remote-decks"][url] = {"url": url, "deckName": deckName}
    mw.addonManager.writeConfig(__name__, config)
    syncDecks()
 
def removeRemoteDeck():
    config = mw.addonManager.getConfig(__name__)
    if not config:
        config = {"remote-decks": {}}
 
    remoteDecks = config["remote-decks"]
    deckNames = [remoteDecks[key]["deckName"] for key in remoteDecks]
 
    if len(deckNames) == 0:
        showInfo("There are currently no remote decks.")
        return
 
    selection, okPressed = QInputDialog.getItem(
        mw,
        "Select a Deck to Unlink",
        "Select a deck to unlink:",
        deckNames,
        0,
        False
    )
 
    if okPressed:
        for key in list(remoteDecks.keys()):
            if selection == remoteDecks[key]["deckName"]:
                del remoteDecks[key]
                break
 
        mw.addonManager.writeConfig(__name__, config)
        showInfo(f"The deck '{selection}' has been unlinked.")
