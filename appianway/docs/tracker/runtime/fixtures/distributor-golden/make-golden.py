"""Golden inputs for distributor from the two QA traces' real distributor inputs.

Usage: python -I make-golden.py <repo>   (writes distributor/src/test/resources-functional/golden/)
"""
import copy, json, os, sys

repo = sys.argv[1]
fx = os.path.join(repo, 'docs/tracker/runtime/fixtures')
out = os.path.join(repo, 'distributor/src/test/resources-functional/golden')
os.makedirs(out, exist_ok=True)


def load(trace):
    return json.load(open(os.path.join(fx, trace, 'input-distributor.json'), encoding='utf-8'))


def write(name, metadata):
    metadata = copy.deepcopy(metadata)
    metadata['bucket'] = 's3-workspace'          # the test workspace (the same bucket in QA: both inttra2-qa-workspace)
    with open(os.path.join(out, name), 'w', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(metadata, indent=2, ensure_ascii=False) + '\n')


fa = load('qa-iftmbf-bk3-minmsc')           # CONTRL FA to CU2100, IPF 2366
confirm = load('qa-iftmbc-2docs-sa-confirm-max')   # X12 301 to CU2100, IPF 1709, fileNameToken.* projections
write('pickup-fa.json', fa)
write('pickup-301.json', confirm)

zipped = copy.deepcopy(fa)
zipped['projections']['outboundIntegrationProfileFormatId'] = '9001'
write('pickup-zip.json', zipped)

optional = copy.deepcopy(fa)
for k in ('outboundEdiId', 'contextCode', 'inftpfilepickuptime'):
    optional['projections'].pop(k, None)
optional['projections']['reprocess'] = 'true'
write('pickup-optional-metadata.json', optional)

no_ipf = copy.deepcopy(fa)
no_ipf['projections'].pop('outboundIntegrationProfileFormatId')
write('pickup-no-ipf.json', no_ipf)

no_path = copy.deepcopy(fa)
no_path['projections']['outboundIntegrationProfileFormatId'] = '9002'
write('pickup-no-delivery-path.json', no_path)

# The documents in the workspace (any text; one non-ASCII character to show bytes are kept)
open(os.path.join(out, 'document-fa.txt'), 'w', encoding='utf-8', newline='\n').write(
    "UNB+UNOC:3+INTTRA+CU2100+261119:1755+100029604001'UNH+1+CONTRL:D:3:UN'UCI+MIN1120000001+CU2100+INTTRA+7'UNT+3+1'UNZ+1+100029604001'é\n")
open(os.path.join(out, 'document-301.txt'), 'w', encoding='utf-8', newline='\n').write(
    'ISA*00*          *00*          *ZZ*INTTRA         *ZZ*CU2100         *261119*0008*U*00401*123456789*0*P*>~\nST*301*0001~B1**2011057403*20261119*A~SE*3*0001~\n')
print(fa['fileName'], confirm['fileName'])
