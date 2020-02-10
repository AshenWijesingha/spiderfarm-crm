from django.conf.urls import url
from . import views

app_name = 'spiderfarm'

urlpatterns = [
    url(r'^add/domain/$', views.CreateOrUpdateDomain.as_view()),
    url(r'^add/geoip/$', views.CreateOrUpdateGeoIp.as_view()),
    url(r'^add/ssl/$', views.UpdateSslData.as_view()),
    url(r'^add/signatures/$', views.UpdateSignatureData.as_view()),
    url(r'^pending-zones/$', views.CheckPendingZones.as_view()),
    url(r'^spider-jobs', views.SpiderJobStatus.as_view()),
    url(r'^import', views.ImportDomainsView.as_view()),
]

