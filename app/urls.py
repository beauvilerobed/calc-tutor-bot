from django.urls import path
from . import views

app_name = 'app'

urlpatterns = [
    path('', views.index),
    path('input/', views.input),
    path('reference/', views.reference_guide),
    path('card/<card_name>', views.return_result_as_card),
]
handler404 = 'app.views.handler404'
handler500 = 'app.views.handler500'
