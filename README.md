# Smart Document Search

Smart Document Search is a Django-based application that provides API endpoints for managing and searching PDF documents using AI-powered text embedding and search capabilities.

## Features

API operations support for:
- PDF document upload
- Document search using vector similarity
- Document summarization
- Document deletion

## Prerequisites

- Python 3.8+
- Pip (Python package installer)
- OpenAI API key
- Pinecone API key

All other dependencies are listed in `requirements.txt` and will be installed during the setup process.

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/smart-doc-search.git
   cd smart-doc-search
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Copy the `.env.example` file to `.env` and fill in your API keys:
   ```
   cp .env.example .env
   ```

5. Run migrations:
   ```
   python manage.py migrate
   ```

6. Create a `documents` folder in the project root to store uploaded files.

## Usage

1. Start the Django development server:
   ```
   python manage.py runserver
   ```

2. Access the API endpoints:
   - Upload a document: POST `/api/upload/`
   - Search documents: POST `/api/search/`
   - Summarize a document: POST `/api/summarize/`
   - Delete a document: DELETE `/api/delete/<document_id>/`

## API Documentation

### Upload a Document
- Endpoint: POST `/api/upload/`
- Request: Multipart form data with 'file' field containing the PDF document
- Response: JSON object with document details

### Search Documents
- Endpoint: POST `/api/search/`
- Request: JSON object with 'query' field
- Response: List of matching documents with relevance scores

### Summarize a Document
- Endpoint: POST `/api/summarize/`
- Request: JSON object with 'document_id' field
- Response: JSON object with document summary

### Delete a Document
- Endpoint: DELETE `/api/delete/<document_id>/`
- Response: Confirmation of deletion