from rest_framework import serializers
from .models import Lead
from datetime import datetime

class StatsSerializer(serializers.Serializer):
    stat_type = serializers.CharField(required=True, max_length=100)
    data_type = serializers.CharField(required=True, max_length=100)

class CrawlUpdateSerializer(serializers.Serializer):
    task_id = serializers.CharField(required=True, max_length=100)
    crawler_status = serializers.CharField(required=True, max_length=100)
    crawler_count = serializers.IntegerField(required=True)
    total_crawlers = serializers.IntegerField(required=True)
    crawler_progress = serializers.CharField(required=True, max_length=100)
    progress_total = serializers.IntegerField(required=True)
    section_progress = serializers.CharField(required=True, max_length=100)
    section_total = serializers.IntegerField(required=True)
