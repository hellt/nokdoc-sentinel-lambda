import json
import os
import smtplib
import sys
from email.mime.text import MIMEText
from pprint import pprint

import boto3

here = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(here, "vendored"))

import requests


def check(event, context):

    if not os.environ.get('NOKDOC_MAIL_PWD'):
        raise Exception('Password to nokdoc mailbox has not been provided')
    # entry point for un-auth access to docs -- https://support.alcatel-lucent.com/portal/web/support
    # then go select some product and click on Manual and guides section
    # this will open https://infoproducts.alcatel-lucent.com/cgi-bin/doc_list.pl
    # where with code explorer it is possible to see all the actual doc_name == doc_id pairs.
    DOC_ID = {'nuage-vsp': '1-0000000000662',
              'nuage-vns': '1-0000000004080',
              '1350oms': '1-0000000003304',
              '7850vsa': '1-0000000004076',
              '7850vsg': '1-0000000004076',
              '7850-8vsg': '1-0000000000459',
              '5620sam': '1-0000000002372',
              '7210sas': '1-0000000003348',
              '7450ess': '1-0000000002317',
              '7705sar': '1-0000000002735',
              '7750sr': '1-0000000002238',
              '7950xrs': '1-0000000003922',
              'vsr': '1-0000000004075'
              }

    # API endpoint for querying docs
    GET_DOC_URL = 'https://infoproducts.alcatel-lucent.com/cgi-bin/get_doc_list.pl'

    def get_rels(s, product_id):
        "returns a list of available releases for a given product"

        params = {'entry_id': product_id}
        return s.get(GET_DOC_URL, params=params).json()['proddata']['release']

    def send_email(new_rels):
        msg = MIMEText('New releases are available: {}'.format(new_rels))
        msg['From'] = "NokDoc bot <nokdoc@nuageteam.net>"
        msg['To'] = "Roman Dodin <dodin.roman@gmail.com>"
        msg['Subject'] = "New releases for NokDoc notification"

        with smtplib.SMTP_SSL('smtp.yandex.ru') as s:
            s.login('nokdoc@nuageteam.net', os.environ.get('NOKDOC_MAIL_PWD'))
            s.send_message(msg)

    s = requests.session()
    s3 = boto3.resource('s3')
    bucket = s3.Bucket('rdodin')

    # getting current available releases
    current_rels = {}
    for product_name, product_id in DOC_ID.items():
        rels = get_rels(s, product_id)
        current_rels[product_name] = rels

    if event.get('pathParameters') and ('regenerate' in event.get('pathParameters').get('command')):
        print("regenerating releases_current.json file")
        bucket.put_object(
            Key='serverless/nokdoc-sentinel/releases_current.json',
            Body=json.dumps(current_rels))
        return 0

    # reading a file in S3 bucket
    releases_last_applied_f = bucket.Object(
        'serverless/nokdoc-sentinel/releases_current.json').get()
    releases_last_applied_dict = json.loads(
        releases_last_applied_f['Body'].read())

    # dict to store new releases which have been fetched from doc portal
    # and are missing from locally stored file with last fetched releases
    new_rels = {}
    for p_name, rel_list in current_rels.items():
        # intersection of sets gets us new releases available
        diff = set(rel_list) - set(releases_last_applied_dict[p_name])
        if diff:
            new_rels[p_name] = diff

    # if there are new releases found, fire an email notification
    if new_rels:
        send_email(new_rels)
