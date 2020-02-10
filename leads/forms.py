import csv
import json
import re

import openpyxl
from django import forms
import pandas as pd

from common.models import Attachments, Comment
from leads.models import Lead
from teams.models import Teams
from django.conf import settings

class LeadForm(forms.ModelForm):
    teams_queryset = []
    teams = forms.MultipleChoiceField(choices=teams_queryset)

    def __init__(self, *args, **kwargs):
        assigned_users = kwargs.pop('assigned_to', [])
        super(LeadForm, self).__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs = {"class": "form-control"}
        self.fields['first_name'].required = False
        self.fields['last_name'].required = False

        if assigned_users:
            self.fields['assigned_to'].queryset = assigned_users

        self.fields['assigned_to'].required = False

        for key, value in self.fields.items():
            if key == 'phone':
                value.widget.attrs['placeholder'] =\
                    'Enter phone number with country code'
            else:
                value.widget.attrs['placeholder'] = value.label

        self.fields['first_name'].widget.attrs.update({
            'placeholder': 'First Name'})
        self.fields['last_name'].widget.attrs.update({
            'placeholder': 'Last Name'})
        self.fields['phone'].widget.attrs.update({
            'placeholder': '+1-123-456-7890'})
        self.fields["teams"].choices = [(team.get('id'), team.get('name')) for team in Teams.objects.all().values('id', 'name')]
        self.fields["teams"].required = False

    class Meta:
        model = Lead
        fields = ('assigned_to', 'first_name',
                  'last_name', 'domain',
                  'phone', 'email', 'status',
                  'teams', 
                  )


class LeadCommentForm(forms.ModelForm):
    comment = forms.CharField(max_length=255, required=True)

    class Meta:
        model = Comment
        fields = ('comment', 'lead', 'commented_by')


class LeadAttachmentForm(forms.ModelForm):
    attachment = forms.FileField(max_length=1001, required=True)

    class Meta:
        model = Attachments
        fields = ('attachment', 'lead')

email_regex = '^[_a-zA-Z0-9-]+(\.[_a-zA-Z0-9-]+)*@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*(\.[a-zA-Z]{2,4})$'

def csv_doc_validate(document):
    print('-- inside leads.forms.inside csv_doc_validate --')
    invalid_row = []
    # read in CSV to pandas 
    print('-- reading document var to pandas --')
    uploaded_data = pd.read_csv(document)
    # this stores all the failed csv contacts
    failed_leads_csv = []
    csv_headers = list(uploaded_data.columns)
    print('-- header columns in uploaded csv: %s --' % csv_headers)
    # required_headers = ["domain"]
    required_header = "domain"
    
    if required_header not in csv_headers:
        missing_headers_str = ', '.join(required_headers)
        message = 'Missing required headers: %s' % (missing_headers_str)
        return {"error": True, "message": message}

    print('-- cleaning domain column data, initial count: %s --' % len(uploaded_data))
    domain_col = pd.DataFrame(uploaded_data,columns=['domain'])
    print('-- length of domain_col: %s --' % len(domain_col))

    # remove any non .com domains
    com_domains = domain_col[domain_col.domain.str.endswith('.com')]
    print('-- kept only .com domains: %s --' % len(com_domains))
    no_www = com_domains.replace('www\.','', regex=True)
    clean_domains = no_www.replace('\*\.','', regex=True)

    domain_list = clean_domains.values.tolist()

    print('-- length of domain_list: %s --' % len(domain_list))

    return {"error": False, "validated_rows": domain_list, "invalid_rows": invalid_row, "headers":csv_headers,
        "failed_leads_csv": failed_leads_csv}

def get_validated_rows(wb, sheet_name, validated_rows, invalid_rows):
    # headers = ["first name", "last name", "email"]
    # required_headers = ["first name", "last name", "email"]
    headers = ["title"]
    required_headers = ["title"]
    work_sheet = wb.get_sheet_by_name(name=sheet_name)
    for y_index, row in enumerate(work_sheet.iter_rows()):
        if y_index == 0:
            missing_headers = set(required_headers) - \
                set([str(cell.value).lower() for cell in row])
            if missing_headers:
                missing_headers_str = ', '.join(missing_headers)
                message = "Missing headers: %s %s" % (
                    missing_headers_str, sheet_name)
                return {"error": True, "message": message}
            continue
        elif not ''.join(str(cell.value) for cell in row):
            continue
        else:
            temp_row = []
            invalid_row = []
            for x_index, cell in enumerate(row):
                try:
                    headers[x_index]
                except IndexError:
                    continue
                if headers[x_index] in required_headers:
                    if not cell.value:
                        # message = 'Missing required \
                        #             value %s for row %s in sheet %s'\
                        #     % (headers[x_index], y_index + 1, sheet_name)
                        # return {"error": True, "message": message}
                        invalid_row.append(headers[x_index])
                temp_row.append(cell.value)
            if len(invalid_row) > 0:
                invalid_rows.append(temp_row)
            else:
                if len(temp_row) >= len(required_headers):
                    validated_rows.append(temp_row)
    return validated_rows, invalid_rows


def xls_doc_validate(document):
    wb = openpyxl.load_workbook(document)
    sheets = wb.get_sheet_names()
    validated_rows = []
    invalid_rows = []
    for sheet_name in sheets:
        validated_rows, invalid_rows = get_validated_rows(
            wb, sheet_name, validated_rows, invalid_rows)
    return {"error": False, "validated_rows": validated_rows, "invalid_rows": invalid_rows}


def import_document_validator(document):
    try:
        # dialect = csv.Sniffer().sniff(document.read(1024).decode("ascii"))
        document.seek(0, 0)
        return csv_doc_validate(document)
    except Exception as e:
        print(e)
        try:
            return xls_doc_validate(document)
        except Exception as e:
            print(e)
            return {"error": True, "message": "-- Invalid headers. CSV must have 'domain' column --"}


class LeadListForm(forms.Form):
    leads_file = forms.FileField(required=False)

    def __init__(self, *args, **kwargs):
        super(LeadListForm, self).__init__(*args, **kwargs)
        self.fields['leads_file'].widget.attrs.update({
            "accept": ".csv,.xls,.xlsx,.xlsm,.xlsb,.xml",
        })
        self.fields['leads_file'].required = True
        if self.data.get('leads_file'):
            self.fields['leads_file'].widget.attrs.update({
                "accept": ".csv,.xls,.xlsx,.xlsm,.xlsb,.xml",
            })

    def clean_leads_file(self):
        print('-- inside leads.forms.clean_leads_files --')
        document = self.cleaned_data.get("leads_file")
        if document:
            print('-- document passed through --')
            data = import_document_validator(document)
            if data.get("error"):
                raise forms.ValidationError(data.get("message"))
            else:
                self.validated_rows = data.get("validated_rows", [])
                self.invalid_rows = data.get("invalid_rows", [])

                if len(self.validated_rows) == 0:
                    raise forms.ValidationError("-- CSV file is empty, no rows found --")

                if len(self.validated_rows) > settings.IMPORT_MAX:
                    raise forms.ValidationError("-- Cannot upload CSV with more than %s rows --" % settings.IMPORT_MAX)
        return document




