import streamlit as st
import pandas as pd
from datetime import datetime
from fillpdf import fillpdfs
import os
from pathlib import Path
import requests
import base64
import io

st.set_page_config(
    page_title="KP-Admin",
    page_icon="📄",
    layout="centered",
    initial_sidebar_state="expanded"
)

# Repository details
st.session_state.repo_url = st.secrets['forgejo']['repo_url']
st.session_state.api_base = st.secrets['forgejo']['api_base']
st.session_state.branch = "main"  # Adjust if the branch is different
st.session_state.auth = (st.secrets['forgejo']['username'], st.secrets['forgejo']['password'])
st.session_state.owner = st.secrets['forgejo']['owner']
st.session_state.repo = st.secrets['forgejo']['repo']


def fetch_records(file_path="assets/form_records.csv", header=0):
    """
    Function to fetch csv spreadsheets

    Parameters:
        -file_path(str): The path to the subfolder (e.g., 'master.csv').
        -header(int or None): Indicate the index of the csv headers. Default = 0
    Returns:
        -pandas.dataframe: The csv file as a Pandas DataFrame
    """
    raw_url = f"{st.session_state.repo_url}/raw/{st.session_state.branch}/{file_path}"
    try:
        response = requests.get(raw_url, auth=st.session_state.auth)
        if response.status_code == 200:
            return pd.read_csv(io.StringIO(response.content.decode('utf-8')), header=header)
        else:
            st.error(f"Failed to fetch {file_path}. Status code: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None


def post_to_repo(pdf_path, file_path, name="Researcher", message=None):
    """
    The function to post a filled PDF to the repository.

    Parameters:
        - pdf_path (str): The local path to the filled PDF file
        - file_path (str): The path where the PDF will be posted in the Forgejo repository
        - name (str): Name of the person submitting the file
        - message (str): The commit message for the upload
    Return:
        - A success message if it goes well or an error message if fails.
    """
    # Read the PDF file and encode it to base64
    with open(pdf_path, 'rb') as pdf_file:
        pdf_content = pdf_file.read()
        content = base64.b64encode(pdf_content).decode()

    url = f"{st.session_state.api_base}/repos/{st.session_state.owner}/{st.session_state.repo}/contents/{file_path}"
    if message is None:
        message = f"PDF uploaded by {name} at {datetime.now().strftime('%Y-%m-%d-%H-%m')}"

    payload = {
        "message": message,
        "content": content,
        "branch": st.session_state.branch
    }
    response = requests.post(url, json=payload, auth=st.session_state.auth)
    if response.status_code in (200, 201):
        st.success(f"PDF correctly submitted for review: {message}")
        return True
    else:
        st.error(f"Failed to commit: {response.text}")
        st.session_state['success'] = False
        return False


def update_repo_file(file_path, new_content, name="Researcher", commit_message=None, **to_csv_kwargs):
    """
    Updates or creates a CSV file in a Forgejo repository.

    Parameters:
    - file_path (str): The path to the CSV file in the repository (e.g., 'data/example.csv').
    - new_content (pd.DataFrame): The new CSV content as a Pandas DataFrame.
    - commit_message (str): The commit message for the update.
    - **to_csv_kwargs: Additional keyword arguments to pass to DataFrame.to_csv().

    Returns:
    - bool: True if the update was successful, False otherwise.

    Note:
    - The 'path_or_buf' argument in to_csv_kwargs is ignored, as the function always generates a string.
    """
    # Check if new_content is a DataFrame
    if not isinstance(new_content, pd.DataFrame):
        st.error("new_content must be a Pandas DataFrame")
        return False

    # Construct the API URL using session state variables
    url = f"{st.session_state.api_base}/repos/{st.session_state.owner}/{st.session_state.repo}/contents/{file_path}"

    # Step 1: Try to retrieve the current file info to get the SHA
    try:
        response = requests.get(url, auth=st.session_state.auth)
        if response.status_code == 200:
            # File exists, extract the SHA
            contents = response.json()
            sha = contents['sha']
        elif response.status_code == 404:
            # File doesn’t exist, we’ll create it (no SHA needed)
            sha = None
        else:
            # Unexpected status code
            st.error(f"Error retrieving file info: {response.status_code} - {response.text}")
            return False
    except requests.RequestException as e:
        st.error(f"Failed to fetch file info: {e}")
        return False

    # Step 2: Convert DataFrame to CSV string
    to_csv_kwargs.pop('path_or_buf', None)  # Ensure path_or_buf is not set
    csv_string = new_content.to_csv(**to_csv_kwargs, index=False)

    # Step 3: Prepare the new content by encoding it to base64
    content_bytes = csv_string.encode('utf-8')
    content_base64 = base64.b64encode(content_bytes).decode('utf-8')

    # Step 4: Build the request body for the PUT request
    if not commit_message:
        commit_message = f"Edited by {name} at {datetime.now().strftime('%Y-%m-%d-%H-%m')}"
    data = {
        "message": commit_message,
        "content": content_base64
    }
    if sha:
        data["sha"] = sha  # Include SHA only if updating an existing file

    # Step 5: Send the PUT request to update or create the file
    try:
        response = requests.put(url, json=data, auth=st.session_state.auth)
        if response.status_code in [200, 201]:
            # 200 for update, 201 for create
            st.success("File updated successfully.")
            return True
        else:
            st.error(f"Failed to update file: {response.status_code} - {response.text}")
            return False
    except requests.RequestException as e:
        st.error(f"Failed to update file: {e}")
        return False


st.title("Poduska's Lab Administration")

# Ensure assets directory exists
ASSETS_DIR = "assets"
Path(ASSETS_DIR).mkdir(exist_ok=True)
INPUT_PDF = os.path.join(ASSETS_DIR, "f100d_e_fillable.pdf")
OUTPUT_PDF = os.path.join(ASSETS_DIR, "filled_form.pdf")
CSV_FILE = os.path.join(ASSETS_DIR, "form_records.csv")

# Get form fields
form_fields = list(fillpdfs.get_form_fields(INPUT_PDF).keys())

# Initialize session state
if "f100d_e" not in st.session_state:
    st.session_state["f100d_e"] = {}


# Option 1: Download blank PDF
st.subheader("Download Blank Form")
with open(INPUT_PDF, "rb") as file:
    st.download_button(
        label="Download Blank PDF",
        data=file,
        file_name="f100d_e_fillable.pdf",
        mime="application/pdf"
    )

# Option 2: Fill form via Streamlit
st.subheader("Fill Form Online")
with st.form(key="f100d_e_form"):
    st.write("#### NSERC f100d_e Form")
    trainee_name = st.text_input("Trainee Name")
    name = st.text_input("Name")
    department = st.text_input("Department")
    institution = st.text_input("Institution")
    date = datetime.now().strftime("%Y-%m-%d")
    signature_text = name  # Fallback: use name as signature text

    submit_button = st.form_submit_button("Submit and Generate PDF")

    if submit_button:
        # Map inputs to form fields
        inputs = [trainee_name, name, department, institution, signature_text, date]
        for input_value, field in zip(inputs, form_fields):
            st.session_state["f100d_e"][field] = input_value
        st.write("Form Data:", st.session_state["f100d_e"])

        # Fill form fields
        fillpdfs.write_fillable_pdf(
            input_pdf_path=INPUT_PDF,
            output_pdf_path=OUTPUT_PDF,
            data_dict=st.session_state["f100d_e"]
        )

        # Update form_records.csv
        new_record = {
            "name": name,
            "form": "f100d_e",
            "signed_on": date
        }
        df = fetch_records()
        # Append new record
        df = pd.concat([df, pd.DataFrame([new_record])], ignore_index=True)
        # Save updated CSV
        record_success = update_repo_file(new_content=df, file_path="assets/form_records.csv", name=name)

        # Post the filled PDF to the repository
        pdf_repo_path = f"assets/filled_forms/f100d_e_{name}_{date}.pdf"
        pdf_success = post_to_repo(pdf_path=OUTPUT_PDF, file_path=pdf_repo_path, name=name)

        if record_success and pdf_success:
            st.write("Visit the assets folder in the forms repository if you have access:")
            st.link_button("Visit Records", "https://206-12-100-80.cloud.computecanada.ca/acbc-repo/poduska-lab/KPAdmin")


# Download filled PDF outside the form
if os.path.exists(OUTPUT_PDF):
    with open(OUTPUT_PDF, "rb") as file:
        st.download_button(
            label="Download Filled PDF",
            data=file,
            file_name="filled_form.pdf",
            mime="application/pdf"
        )

# Clean up temporary files on page refresh (only if they exist)
if os.path.exists(OUTPUT_PDF):
    os.remove(OUTPUT_PDF)