from django.urls import path
from .views import DocumentUploadView, summarize_document, search_documents, delete_document
urlpatterns = [
    path('upload/', DocumentUploadView.as_view(), name='file-upload'),
    path('summarize/', summarize_document, name='summarize-document'),
    path('search/', search_documents, name='search-document'),
    path('documents/<int:document_id>/', delete_document, name='delete-document'),
]