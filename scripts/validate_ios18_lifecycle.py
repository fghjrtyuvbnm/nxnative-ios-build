"""Run exact-baseline and candidate lifecycle contracts on native Metal."""
import json,pathlib,subprocess,sys,os
from patch_ios18_lifecycle import candidate

def main(out):
    kit=pathlib.Path(__file__).resolve().parents[1];out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    baseline=(kit/'tests/fixtures/ios18_metal_before_lifecycle.h').read_text()
    if (kit/'runtime/ios18_metal.h').read_text()!=candidate(baseline):raise ValueError('Production adapter differs from the tested candidate')
    reports={}
    for label,text in [('baseline',baseline),('candidate',candidate(baseline))]:
        (out/'adapter-under-test.h').write_text(text)
        binary=out/label
        subprocess.run(['xcrun','clang','-fobjc-arc','-O1','-w','-mmacosx-version-min=15.0','-I'+str(out),str(kit/'runtime/ios18_lifecycle_test.m'),'-framework','Foundation','-framework','Metal','-framework','QuartzCore','-o',str(binary)],check=True)
        result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=30,env=dict(os.environ,MTL_DEBUG_LAYER='1'))
        if result.returncode not in (0,42):raise RuntimeError(label+' native contract did not complete: '+result.stderr[-1500:])
        report=json.loads(result.stdout);reports[label]=report
        print(label,json.dumps(report),flush=True)
        if label=='baseline':
            if result.returncode!=42 or report['independent_classic_queues'] or report['cross_queue_completed_without_rescue']:raise ValueError('Expected original queue contract failure absent')
        elif result.returncode!=0:raise ValueError('Candidate lifecycle contract failed')
    (out/'lifecycle-report.json').write_text(json.dumps(reports,indent=2))
    print('Baseline RED and candidate GREEN for classic queue isolation and weak-resource lifetime',flush=True)

if __name__=='__main__':main(sys.argv[1])
