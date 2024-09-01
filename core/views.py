from django.shortcuts import render, get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.decorators import api_view
from rest_framework import status

from .serializers import DocumentSerializer
from .models import Document

import PyPDF2

import openai
from openai import OpenAI
from pinecone.grpc import PineconeGRPC as Pinecone
from pinecone import ServerlessSpec

import os
from dotenv import load_dotenv
import mimetypes

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=openai.api_key)
pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index_name = "smart-doc-search"

# Update the dimension to match the embedding size (1536 for text-embedding-ada-002)
if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=1536,
        metric="cosine",
        spec=ServerlessSpec(cloud='aws', region='us-east-1')
    ) 

def get_embedding(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-ada-002"  # or your preferred model
    )
    return response.data[0].embedding

class DocumentUploadView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *args, **kwargs):
        file_serializer = DocumentSerializer(data=request.data)
        
        if file_serializer.is_valid():
            file = request.FILES.get('file')
            
            if not file:
                return Response({
                    "error": "Upload failed"
                }, status=status.HTTP_400_BAD_REQUEST)

            # Check file type
            file_type, _ = mimetypes.guess_type(file.name)
            if file_type != 'application/pdf':
                return Response({
                    "error": "Upload failed"
                }, status=status.HTTP_400_BAD_REQUEST)

            document = file_serializer.save()
            
            content = self.extract_text(document.file.path)
            
            embedding = get_embedding(content)
            
            # Create more informative metadata
            metadata = {
                "content": content[:1000],
                "file_name": document.file.name,
                "word_count": len(content.split()),
                "upload_date": document.uploaded_at.isoformat()
            }
            
            # Upsert the embedding to Pinecone with improved metadata
            try:
                pc.Index(index_name).upsert(vectors=[(str(document.id), embedding, metadata)])
            except Exception as e:
                # If Pinecone upsert fails, delete the saved document and return error
                document.delete()
                print(f"Error upserting to Pinecone: {str(e)}")
                return Response({
                    "error": "Upload failed"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            return Response(file_serializer.data, status=status.HTTP_201_CREATED)
        else:
            print(f"Upload failed: {file_serializer.errors}")
            return Response({
                "error": "Upload failed"
            }, status=status.HTTP_400_BAD_REQUEST)

    def extract_text(self, file_path):
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            content = ""
            for page in reader.pages:
                content += page.extract_text()
        return content

@api_view(['POST'])
def search_documents(request):
    try:
        query = request.data.get('query')
        if not query:
            return Response({
                "error": "Search operation failed"
            }, status=status.HTTP_400_BAD_REQUEST)

        query_embedding = get_embedding(query)

        search_results = pc.Index(index_name).query(
            vector=query_embedding,
            top_k=10,
            include_metadata=True
        )

        processed_results = []
        seen_content = set()
        min_score_threshold = 0.8

        for match in search_results['matches']:
            score = match['score']
            content_preview = match['metadata']['content']

            if score >= min_score_threshold and content_preview not in seen_content:
                try:
                    document = Document.objects.get(id=int(match['id']))
                    processed_results.append({
                        'id': match['id'],
                        'score': score,
                        'content_preview': content_preview,
                        'file_name': document.file.name  # Make sure this is included
                    })
                    seen_content.add(content_preview)
                except ObjectDoesNotExist:
                    # If document doesn't exist in DB, skip it
                    continue

        processed_results.sort(key=lambda x: x['score'], reverse=True)

        return Response({'results': processed_results[:5]})

    except Exception as e:
        print(f"Search operation failed: {str(e)}")
        return Response({
            "error": "Search operation failed"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['DELETE'])
def delete_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)

    # Delete the document from Pinecone first
    try:
        index = pc.Index(index_name)
        delete_response = index.delete(ids=[str(document_id)])
        
        if not delete_response:
            return Response({
                "error": "Document delete operation failed"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except AttributeError as e:
        print(f"AttributeError when deleting document from Pinecone: {str(e)}. Available methods on index: {dir(index)}")
        return Response({
            "error": "Document delete operation failed"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        print(f"Error deleting document from Pinecone: {str(e)}. Type: {type(e).__name__}")
        return Response({
            "error": "Document delete operation failed"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # If Pinecone deletion was successful, proceed with local deletion
    if document.file and os.path.isfile(document.file.path):
        try:
            os.remove(document.file.path)
        except OSError as e:
            return Response({
                "error": "Document delete operation partially failed"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # Delete the document from the database
    document.delete()

    return Response({"message": "Document successfully deleted"}, status=status.HTTP_204_NO_CONTENT)

@api_view(['POST'])
def summarize_document(request):
    try:
        document_id = request.data.get('document_id')
        document_name = request.data.get('document_name')

        if document_id:
            document = get_object_or_404(Document, id=document_id)
        elif document_name:
            document = get_object_or_404(Document, file__iexact=document_name)
        else:
            return Response({
                "error": "Please provide either document_id or document_name"
            }, status=status.HTTP_400_BAD_REQUEST)

        with open(document.file.path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            content = ""
            for page in reader.pages:
                content += page.extract_text()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Summarize the following document:"},
                {"role": "user", "content": content}
            ],
            max_tokens=150
        )

        return Response({'summary': response.choices[0].message.content.strip()})

    except PyPDF2.errors.PdfReadError as e:
        print(f"Error reading PDF: {str(e)}")
        return Response({
            "error": "Summarization failed"
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        print(f"Summarization failed: {str(e)}")
        return Response({
            "error": "Summarization failed"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





