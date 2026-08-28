from django.urls import path
from . import views

urlpatterns = [

    path('', views.upload_document, name='upload'),

    path('dashboard/', views.dashboard, name='dashboard'),

    path('search/', views.search_documents, name='search'),

    path('translate/', views.translate_text, name='translate'),

    path("download-summary/<int:doc_id>/", views.download_summary, name="download_summary"),

    path('login/', views.login_view, name='login'),

    path('register/', views.register_view, name='register'),

    path('logout/', views.logout_view, name='logout'),

    path('documents/', views.documents_view, name='documents'),
    
    path('audio/', views.audio_view, name='audio'),

]