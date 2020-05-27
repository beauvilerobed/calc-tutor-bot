# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()
from django.urls import path
from django.conf.urls import url, include


# A single dot means that the module or package referenced is 
# in the same directory as the current location. Two dots mean 
# that it is in the parent directory of the current location—that i
# s, the directory above. Three dots mean that it is in the 
# grandparent directory, and so on.
#https://realpython.com/absolute-vs-relative-python-imports/
from . import views

app_name = 'app'

urlpatterns = [
    path('', views.index),

    path('input/', views.input),
    path('table/', views.table),

    path('card/<card_name>', views.eval_card),

    path('card_info/<card_name>', views.get_card_info),

    path('card_full/<card_name>', views.get_card_full)


    # Uncomment the admin/doc line below and add 'django.contrib.admindocs'
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # (r'^admin/(.*)', admin.site.root),
]

handler404 = 'app.views.handler404'
handler500 = 'app.views.handler500'
