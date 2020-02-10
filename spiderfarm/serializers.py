from rest_framework import serializers
from .models import *
import re
from datetime import datetime

def remove_prefix(domain):
    if 'https://' in domain:
        return domain.replace('https://', '')

    if 'http://' in domain:
        return domain.replace('http://', '')


class SslSerializer(serializers.ModelSerializer):
    tld_ext = serializers.StringRelatedField()

    class Meta:
        model = Domain
        fields = ('domain_name',
            'tld_ext',
            'ssl_expire',
            'ssl_issuer_name',
            'ssl_issuer_org_unit',
            'ssl_url',
            'ssl_san',
            'last_ssl_update',
            'ssl_error',
        )
    '''
    def validate_ssl_issuer_name(self, value):
        # Check that the issuer isn't a free cert
        print('-- inside validate_ssl_issuer_name() --')
        bad_issuers = ["aws", "cpanel", "encrypt"]

        print(self)
        print(type(self))
        for issuer in bad_issuers:
            if issuer in value.lower():
                print('-- bad cert issuer detected: %s --' % value)
                self.ssl_error = 'Free cert issuer'
                print('-- added Free cert error to domain --')
                # raise serializers.ValidationError("Free cert issuer found; discarding cert save")

        return value
    '''

    def update(self, instance, validated_data):
        print('-- inside SslSerializer.update() --')
        instance.ssl_expire = validated_data.get('ssl_expire', instance.ssl_expire)

        # clear tags for SSL issuer, then add the ssl issuer name
        instance.ssl_issuer_name.set( validated_data.get('ssl_issuer_name', instance.ssl_issuer_name ))

        instance.ssl_issuer_org_unit = validated_data.get('ssl_issuer_org_unit', instance.ssl_issuer_org_unit)
        instance.ssl_url = validated_data.get('ssl_url', instance.ssl_url)

        # clear all tags from SSL SAN list, then add new data  
        instance.ssl_san.set( validated_data.get('ssl_san', instance.ssl_san) )

        instance.last_ssl_update = datetime.now()
        instance.ssl_error = validated_data.get('ssl_error', instance.ssl_error)

        instance.save()
        return instance


class GeoIpSerializer(serializers.ModelSerializer):
    tld_ext = serializers.StringRelatedField()
    spider_jobs = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model = Domain
        fields = ('domain_name',
            'tld_ext',
            'site_ip',
            'geoip_country',
            'geoip_geocode',
            'last_geoip_update',
            'geoip_error',
            'spider_jobs',
        )

    def create(self, validated_data):
        print('-- inside GeoIP -> create')
        domain_name = validated_data.get('domain_name', '')
        tld_match = re.search(r'http\:\/\/[\w-]+(\.\w+)*$', domain_name)
        
        if tld_match:
            print("extracted tld: " + tld_match.group(1))
            print("domain name: " + domain_name)
            # with extracted tld, make sure its in the db and save
            tld = str(tld_match.group(1))
            try:
                tld_rec = ZoneExtension.objects.get(tld_extension=tld)

                if validated_data.get('spider_jobs', ''):
                    print('-- spider_jobs passed through to GeoIpSerializer.create() --')
                    job_tags = validated_data.pop('spider_jobs')

                instance = Domain.objects.create(tld_ext=tld_rec, last_geoip_update=datetime.now(), **validated_data)

                if job_tags:
                    instance.spider_jobs.add( job_tags )

                # return Domain instance
                return instance

            except ZoneExtension.DoesNotExist:
                print('%s is not a valid ZoneExtension' % tld)


    def update(self, instance, validated_data):
        print('-- inside GeoIpSerializer.update() --')
        instance.geoip_country = validated_data.get('geoip_country', instance.geoip_country)
        instance.geoip_geocode = validated_data.get('geoip_geocode', instance.geoip_geocode)
        instance.site_ip = validated_data.get('site_ip', instance.site_ip)
        instance.geoip_error = validated_data.get('geoip_error', instance.geoip_error)
        instance.last_geoip_update = datetime.now()

        if validated_data.get('spider_jobs', ''):
            print('-- spider_jobs passed through to GeoIpSerializer.update() --')
            job_tags = validated_data.pop('spider_jobs')

        instance.save()

        if job_tags:
            print('-- job_tags parsed out from validated_data --')
            instance.spider_jobs.add( job_tags )

        return instance


class WebSignatureSerializer(serializers.Serializer):
    domain_name = serializers.CharField(max_length=200)
    mx_records = serializers.ListField(
        child=serializers.CharField(max_length=200), 
        required=False
    )

    wp_addons = serializers.ListField(
        child=serializers.CharField(max_length=200), 
        required=False
    )

    server_type = serializers.CharField(max_length=200, required=False)
    site_redirect = serializers.URLField(max_length=200, required=False)
    x_powered_by = serializers.CharField(max_length=200, required=False)
    wp_version = serializers.CharField(max_length=200, required=False)


class DomainSerializer(serializers.ModelSerializer):
    tld_ext = serializers.StringRelatedField()
    spider_jobs = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model = Domain
        fields = ('domain_name',
            'tld_ext',
            'domain_expire',
            'name_servers',
            'domain_registrar',
            'registrant_email',
            'registrar_url',
            'registrant_country',
            'last_whois_update',
            'whois_error',
            'spider_jobs',
        )

    def create(self, validated_data):
        print('-- inside DomainSerializer.create() --')
        domain_name = validated_data.get('domain_name', '')
        # use regex to validate it's a "dot-com" looking string
        tld_match = re.search(r'http\:\/\/[\w-]+(\.\w+)*$', domain_name)

        whois_update=datetime.now()

        if tld_match:
            print("extracted tld: " + tld_match.group(1))
            print("domain name: " + domain_name)
            # with extracted tld, make sure its in the db and save
            tld = str(tld_match.group(1))
            try:
                tld_rec = ZoneExtension.objects.get(tld_extension=tld)

                if validated_data.get('spider_jobs', ''):
                    print('-- spider_jobs passed through to WhoisSerializer.create() --')
                    job_tags = validated_data.pop('spider_jobs')

                # make new Domain object
                instance =  Domain.objects.create(tld_ext=tld_rec, last_whois_update=whois_update, **validated_data)
   
                if job_tags:
                    instance.spider_jobs.add( job_tags )

                return instance

            except ZoneExtension.DoesNotExist:
                print('%s is not a valid ZoneExtension' % tld)

            except Exception as e:
                print(e) 
    
    def update(self, instance, validated_data):
        print('-- inside DomainSerializer.update() --')
        instance.domain_expire = validated_data.get('domain_expire', instance.domain_expire)
        # clear name servers, update tags
        instance.name_servers.set( validated_data.get('name_servers', instance.name_servers) )
        instance.domain_registrar = validated_data.get('domain_registrar', instance.domain_registrar)
        instance.registrant_email = validated_data.get('registrant_email', instance.registrant_email)
        instance.registrar_url = validated_data.get('registrar_url', instance.registrar_url)
        instance.registrant_country = validated_data.get('registrant_country', instance.registrant_country)
        instance.last_whois_update = datetime.now()
        instance.whois_error = validated_data.get('whois_error', instance.whois_error)

        if validated_data.get('spider_jobs', ''):
            print('-- spider_jobs passed through to WhoisSerializer.update() --')
            job_tags = validated_data.pop('spider_jobs')

        instance.save()

        if job_tags:
            print('-- job_tags parsed out from validated_data --')
            instance.spider_jobs.add( job_tags )

        return instance


class PendingZonesSerializer(serializers.Serializer):
    tld_type = serializers.CharField(required=True, max_length=100)
    frag_count = serializers.IntegerField()












 
    











