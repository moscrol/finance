"""Read-only reuse of the serving generation's existing consumer bindings."""
import json
import os
from pathlib import Path
import sys

def initialize(config_path, code_root):
    cfg=json.loads(Path(config_path).read_text())
    cleanup=cfg['consumer_environment_cleanup']
    for key in tuple(os.environ):
        if key.startswith(tuple(cleanup['remove_prefixes'])) or key in cleanup['remove_exact']:
            os.environ.pop(key,None)
    os.environ.update(cfg['workbench_environment'])
    os.environ.update(cfg['rag_environment'])
    os.environ.update(cfg['worker_environment_from_production_call'])
    os.environ['PYTHONDONTWRITEBYTECODE']='1'
    os.environ['PYTHONPATH']=str(code_root)
    sys.path.insert(0,str(code_root))
    return cfg

def effective(cfg):
    from intelligence.services.rag_generation_identity import capture_generation
    from intelligence.services import kb_rag
    from intelligence.paths import default_paths
    paths=default_paths()
    wiki=kb_rag._resolve_rag_wiki(paths.knowledge_wiki)
    code=kb_rag._resolve_code_root(kb_rag.kb_root(wiki))
    python=kb_rag._resolve_rag_python(code)
    standard=kb_rag._resolve_index_dir(kb_rag.kb_root(wiki))
    environment={k:os.environ[k] for k in cfg['rag_environment']}
    for index in (standard,Path(environment['KB_RAG_FULL_INDEX_DIR'])):
        binding=capture_generation(python,code,index,wiki,environment=environment)
        binding.require_available()
        assert binding.managed and binding.generation==cfg['generation_id']
        assert binding.manifest_sha256==cfg['manifest_sha256']
    assert str(wiki)==environment['KB_VAULT']
    assert str(standard)==environment['RAG_INDEX_DIR']
    return {'workbench_wiki':str(paths.knowledge_wiki),'rag_wiki':str(wiki),
        'rag_code':str(code),'rag_python':str(python),'standard_index':str(standard),
        'full_index':environment['KB_RAG_FULL_INDEX_DIR'],'generation':binding.generation,
        'manifest_sha256':binding.manifest_sha256}
