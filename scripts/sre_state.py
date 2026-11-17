"""Estado operativo explícito externo a Helm; no modifica aplicaciones ni datos."""
import argparse
import json
import os
from pathlib import Path
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['prepare','active','inactive','validation-on','validation-off'])
    args=parser.parse_args()
    command=[str(Path(__file__).resolve().parents[1]/'.local/f4/tools/kubectl'),'--context',os.environ['KUBE_CONTEXT'],'-n','retailops-observability']
    existing=subprocess.run(command+['get','configmap','retailops-lab-state','-o','json','--ignore-not-found'],capture_output=True,text=True,check=True).stdout
    if existing:
        state=json.loads(json.loads(existing)['data']['state.json'])
        if args.mode=='prepare':return
    else:
        state={'lab_active':0,'validation':{'api':0,'ml':0}}
    if args.mode=='active':state['lab_active']=1
    if args.mode=='inactive':state={'lab_active':0,'validation':{'api':0,'ml':0}}
    if args.mode in ['validation-on','validation-off']:
        state['validation']={case:int(args.mode=='validation-on') for case in ['api','ml']}
    config={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'retailops-lab-state','namespace':'retailops-observability'},'data':{'state.json':json.dumps(state)}}
    subprocess.run(command+['apply','-f','-'],input=json.dumps(config),text=True,check=True)
    print(json.dumps(state))


if __name__=='__main__':main()
