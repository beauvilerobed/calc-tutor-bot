from django.contrib import admin
from django.urls import path, include
from app.views import ChatBotAppView, ChatBotApiView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('app.urls')),
    path('', ChatBotAppView.as_view(), name='main'),
    path('api/chatbot/', ChatBotApiView.as_view(), name='chatbot'),
]
