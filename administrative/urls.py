from django.conf.urls import *
from django.contrib import admin
from django.urls import path
from leave import urls

urlpatterns = ['',
    # Examples:
    # url(r'^$', 'administrative.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    path('admin/', admin.site.urls)
    #path('^',urls)	#Redirect everything to Leave App

]



