"""Write or verify canonical Sprint 93.2A V2 preregistration."""
import argparse,ast,hashlib,json,subprocess
from pathlib import Path
from mss.analysis.sprint93_confluence_gate_v2_preregistration import Sprint93ConfluenceGateV2Preregistration as C
ROOT=Path(__file__).resolve().parents[1]
SOURCES={"g5":"reports/MSS_Sprint92G5_Confluence_Gate_Research_Closure.json","h6":"reports/MSS_Sprint92H6_Immutable_Development_Research_Closure.json","c2":"reports/MSS_Sprint92C2_Extended_Dataset_Manifest.json"}
OUTPUT=ROOT/"reports/MSS_Sprint93_2A_Confluence_Gate_V2_Preregistration.json"
def git_bytes(spec): return subprocess.run(["git","cat-file","blob",spec],cwd=ROOT,check=True,stdout=subprocess.PIPE).stdout
def sha(path): return hashlib.sha256(git_bytes(f"{C.BASELINE_COMMIT}:{path}")).hexdigest()
def closure():
    pending=list(C.STRATEGY_COMPONENT_ROOTS); found=set()
    while pending:
        path=pending.pop()
        if path in found: continue
        found.add(path); tree=ast.parse(git_bytes(f"{C.BASELINE_COMMIT}:{path}").decode("utf-8-sig"))
        modules=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom) and node.module: modules.append(node.module)
            elif isinstance(node,ast.Import): modules.extend(a.name for a in node.names)
        for module in modules:
            candidate="src/"+module.replace(".","/")+".py"
            if module.startswith("mss.") and subprocess.run(["git","cat-file","-e",f"{C.BASELINE_COMMIT}:{candidate}"],cwd=ROOT).returncode==0 and candidate not in found: pending.append(candidate)
    return tuple(sorted(found))
def canonical(payload): return (json.dumps(payload,indent=2,sort_keys=True,allow_nan=False)+"\n").encode()
def rebuild():
    paths=closure()
    if paths!=C.REQUIRED_STRATEGY_COMPONENT_FILES: raise RuntimeError("transitive internal mss closure differs from frozen universe")
    hashes={p:sha(p) for p in paths}; inputs={k:json.loads(git_bytes(f"{C.BASELINE_COMMIT}:{p}")) for k,p in SOURCES.items()}
    artifact=C().build(inputs["g5"],inputs["h6"],inputs["c2"],hashes); artifact["audit"]["deterministic_rebuild"]=True; artifact["source_git_blob_sha256"]={k:sha(p) for k,p in SOURCES.items()}
    return artifact,{p:sha(p) for p in (*paths,*SOURCES.values())}
def main(argv=None):
    parser=argparse.ArgumentParser(); modes=parser.add_mutually_exclusive_group(required=True); modes.add_argument("--write",action="store_true"); modes.add_argument("--verify",action="store_true"); args=parser.parse_args(argv)
    protected=(*C.REQUIRED_STRATEGY_COMPONENT_FILES,*SOURCES.values())
    if subprocess.run(["git","diff","--quiet",C.BASELINE_COMMIT,"--",*protected],cwd=ROOT).returncode: raise RuntimeError("execution/source content differs from baseline commit")
    artifact,before=rebuild(); rendered=canonical(artifact)
    if args.write:
        if OUTPUT.exists(): raise RuntimeError(f"refusing to overwrite existing report: {OUTPUT}")
        OUTPUT.write_bytes(rendered)
    elif OUTPUT.read_bytes()!=rendered: raise RuntimeError("committed report is not complete canonical rebuild")
    if before!={p:sha(p) for p in protected}: raise RuntimeError("protected Git blob changed during execution")
    if args.verify: print("PREREGISTRATION_VERIFY_PASS")
if __name__=="__main__": main()
