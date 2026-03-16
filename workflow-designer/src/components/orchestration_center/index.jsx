import {useTranslation} from "react-i18next";
import {useEffect, useMemo, useRef, useState} from "react";
import {createWorkflow, getWorkflow} from "@/service/api.js";
import yaml, {dump} from "js-yaml";
import {Activity, FileText, FileWarning, Hash, Layout, Loader2, Plus, Search, Upload} from "lucide-react";
import {createPortal} from "react-dom";

const safeParse = (data) => {
    if (!data) return {};
    if (typeof data === 'object') return data;
    if (typeof data === 'string') {
        try {
            return JSON.parse(data);
        } catch (e) {
            console.warn("JSON Parse Waring: data is not valid JSON,returning empty object.")
            return {};
        }
    }
    return {};
}

const OrchestrationCenter = ({isDark}) => {
    const {t, i18n} = useTranslation();
    const lang = i18n.language;
    const [workflows, setWorkflows] = useState([]);
    const [selectedId, setSelectedId] = useState(null);
    const [searchTerm, setSearchTerm] = useState('');
    const [loading, setLoading] = useState(true);
    const [nodes, setNodes] = useState([]);
    const [edges, setEdges] = useState([]);

    const [rightPanelMode, setRightPanelMode] = useState('yaml');
    const [isAdding, setIsAdding] = useState(false);

    const [showImportModal, setShowImportModal] = useState(false);
    const [importYaml, setImportYaml] = useState('');
    const [importPhenomenon, setImportPhenomenon] = useState('');
    const [toast, setToast] = useState({show: false, msg: '', type: 'error'})
    const fileInput = useRef(null);

    useEffect(() => {
        if (toast.show) {
            const timer = setTimeout(() => setToast({...toast, show: false}), 3000);
            return () => clearTimeout(timer);
        }
    }, [toast.show]);

    const handleAddNew = () => {
        setIsAdding(true);
    }

    const handleSelectWorkflow = (id) => {
        setIsAdding(false);
        setSelectedId(id);
    }

    const fetchData = async () => {
        try {
            setLoading(true);
            const workflowResponse = await getWorkflow();

            const rawList = workflowResponse?.result || [];
            if (!Array.isArray(rawList)) {
                console.error("API Error: Second step returned non-array data");
                setWorkflows([]);
                return;
            }
            const adaptedData = rawList.map(item => ({
                id: item.question_id,
                name: item.question_text || item.phenomenon || 'Untitled Workflow',
                rawText: safeParse(item.worflow),
                trajectory: item.trajectory,
                keyword: item.keyword,
                confirmed: item.confirmed_info
            }));
            setWorkflows(adaptedData);
            if (adaptedData.length > 0) {
                setSelectedId(prev => prev || adaptedData[0].id);
            }
        } catch (e) {
            console.error("Orchestration Fetch Error:", e);
            setWorkflows([]);
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        fetchData();
    }, []);

    const currentWf = useMemo(() =>
            workflows.find(wf => wf.id === selectedId) || null,
        [workflows, selectedId]);

    const yamlString = useMemo(() => {
        if (!currentWf?.rawText || Object.keys(currentWf.rawText).length === 0) return '# No configuration data';
        try {
            return dump(currentWf.rawText);
        } catch (e) {
            return '#Roore generation YAML';
        }
    }, [currentWf]);


    useEffect(() => {
        const trans = tranformWorkflowToReactFlow(currentWf?.rawText);
        setNodes(trans['nodes']);
        setEdges(trans['edges']);
    }, []);

    const filteredWorkflows = useMemo(() => {
        if (!searchTerm.trim()) return workflows;
        return workflows.filter((wf) => wf.name?.toLowerCase().includes(searchTerm.toLowerCase()) || wf.keyword?.toLowerCase().includes(searchTerm.toLowerCase()));
    }, [workflows, searchTerm]);

    const executeImport = async () => {
        try {
            await createWorkflow({
                phenomenon: importPhenomenon,
                workflow: importYaml
            });
            setToast({show: true, msg: t('workflow.import.success', 'Import Successful!'), type: 'success'});
            setShowImportModal(false);
            setImportYaml('');
            setImportPhenomenon('');
            fetchData();
        } catch (e) {
            console.error('Import failed', e);
            setToast({show: true, msg: t('workflow.import.failed', 'Import Failed!'), type: 'error'})
        }
    }

    const yamlToJson = (yamlStr, phenomenon) => {
        try {
            const obj = yaml.load(yamlStr);
            console.log("yaml to json is ", JSON.stringify(obj, null, 2));
            const jsonString = JSON.stringify({"yaml": obj, phenomenon}, null, 2);
            const blob = new Blob([jsonString], {type: 'application/json'});
            const url = URL.createObjectURL(blob);

            const a = document.createElement('a');
            a.href = url;
            a.download = 'workflow.json';
            document.body.appendChild(a);
            a.click();

            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (e) {
            throw new Error(`Yaml parse failed: ${e.message}`);
        }
    }

    const theme = {
        overlay: isDark ? 'bg-zinc-950/60 backdrop-blur-md' : 'bg-slate-900/40 backdrop-blur-sm',
        primaryBtn: isDark ? 'bg-zinc-100 text-zinc-950 hover:bg-white shadow-none' : 'bg-slate-800 text-white hover:bg-slate-900 shadow-slate-200',
        modal: isDark ? 'bg-zinc-900 border-zinc-700/50 shadow=[0_20px_50px_rgba(0,0,0,0.5)] ring-1 ring-white/10' : 'bg-white border-slate-200 shadow-xl',
        input: isDark ? 'bg-zinc-950 border-zinc-700 text-zinc-200 placeholder:text-zinc-600 focus:border-blue-500/50 focus:ring-blue-500/20' : 'bg-slate-200 text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:ring-blue-500/10',
    }

    const ImportModal = (
        <div className={`fixed inset-0 z-[9999] flex items-center justify-center p-4 ${theme.overlay}`}>
            <div className={"absolute inset-0"} onClick={() => setShowImportModal(false)}/>
            <div
                className={`relative w-full max-w-2xl p-7 rounded-[2rem] border transform transition-all animate-in fade-in zoom-in-95 duration-200 ${theme.modal}`}
                style={{maxHeight: '90vh', overflowY: 'auto'}}>
                {isDark && (
                    <div
                        className={"absolute top-0 left-1/2 -translate-x-1/2 w-16 h-1 bg-zinc-700/50 rounded-full mt-2"}/>
                )}
                <div className={"flex items-center gap-4 mb-5"}>
                    <div
                        className={`p-3 rounded-2xl ${isDark ? 'bg-indigo-500/20 text-indigo-400' : 'bg-indigo-50 text-indigo-600'}`}>
                        <Upload className={"w-6 h-6"}/>
                    </div>
                    <div>
                        <h3 className={`text-xl font-extrabold tracking-tight ${isDark ? 'text-zinc-50' : 'text-slate-900'}`}>
                            {t('workflow.import.modalTitle', 'Import Workflow YAML')}
                        </h3>
                        <div className={`h-1 w-8 rounded-full bg-indigo-500 mt-1 ${isDark ? 'opacity-80' : ''}`}/>
                    </div>
                </div>

                <div className={"mb-4"}>
                    <label
                        className={`block text-xs font-black uppercase tracking-widest mb-2 ml-1 ${isDark ? 'text-zinc-400' : 'text-slate-500'}`}>
                        Workflow YAML
                    </label>
                    <textarea value={importYaml}
                              onChange={(e) => setImportYaml(e.target.value)}
                              placeholder={"Paste your YAML configuration here..."}
                              className={`w-full px-4 py-4 rounded-2xl border outline-none transition-all duration-200 resize-none h-48 font-mono text-sm ${theme.input}`}
                    />
                </div>

                <div className={"mb-6"}>
                    <label
                        className={`block text-xs font-black uppercase tracking-widest mb-2 ml-1 ${isDark ? 'text-zinc-400' : 'text-slate-500'}`}>
                        Use Case (Phenomenon)
                    </label>
                    <textarea value={importPhenomenon}
                              onChange={(e) => setImportPhenomenon(e.target.value)}
                              placeholder={"Describe the use case..."}
                              className={`w-full px-4 py-4 rounded-2xl border outline-none transition-all duration-200 resize-none h-20 font-medium ${theme.input}`}
                    />
                </div>

                <div className={"flex gap-4"}>
                    <button onClick={() => {
                        setShowImportModal(false);
                        setImportYaml('');
                        setImportPhenomenon('');
                    }}
                            className={`flex-1 px-4 py-3 text-sm font-bold rounded-2xl transition-all active:scale-95 ${isDark ? 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-900'}`}>
                        {t('common.cancel', 'Cancel')}
                    </button>
                    <button onClick={executeImport}
                            disabled={!importYaml.trim() || !importPhenomenon.trim()}
                            className={`flex-1 px-4 py-3 text-sm font-black rounded-2xl transition-all active:scale-95 shadow-lg ${isDark ? 'bg-zinc-100 text-zinc-950 hover:bg-white shadow-zinc-950/20' : 'bg-slate-900 text-white hover:bg-slate-800 shadow-slate-200'} disabled:opacity-20 disabled:grayscale disabled:scale-100`}>
                        {t('common.import', 'Import & Save')}
                    </button>
                </div>
            </div>
        </div>
    );

    return (
        <div
            className={"h-full p-8 flex items-stretch gap-8 max-w-[1650px] mx-auto w-full transition-all animate-in fade-in duration-700 overflow-hidden font-sans bg-zinc-50 dark:bg-zinc-950"}>
            <div className={"w-[350px] flex flex-col gap-6 shrink-0 min-h-0"}>
                <div
                    className={"bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded=[2.5rem] p-6 shadow-xl border-t-4 border-t-blue-600 shrink-0"}>
                    <div className={"flex items-center justify-between gap-2 mb-4"}>
                        <h1 className={"text-xl font-black text-zinc-900 dark:text-white uppercase tracking-tight truncate leading-tight "}>
                            {t('orchestration.title', 'Orchestration')}
                        </h1>

                        <div className={"flex items-center gap-2"}>
                            <button onClick={() => fileInput.current.click()}
                                    className={`p-2 px-3 flex items-center gap-1.5 rounded-xl transition-all group shrink-0 shadow-sm ${isDark ? 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-white border border-zinc-700' : 'bg-white text-zinc-700 border border-zinc-200 hover:bg-zinc-50 hover:text-indigo-600'}`}
                                    title={'Import YAML'}
                            >
                                <Upload size={16}
                                        className={"group-hover:-translate-y-0.5 transition-transform shrink-0"}/>
                                <span className={"text-xs font-bold whitespace-nowrap uppercase tracking-wider"}>
                                    Import
                                </span>
                            </button>
                            <input type={'file'}
                                   accept={'.json'}
                                   ref={fileInput}
                                   onChange={(e) => {
                                       if (e.target.files && e.target.files[0]) {
                                           const file = e.target.files[0];
                                           if (!file.name.endsWith('.json') || file.type !== 'application/json') {
                                               setToast({
                                                   show: true,
                                                   msg: t('orchestration.invalid_file'),
                                                   type: 'error'
                                               });
                                           } else {
                                               const reader = new FileReader();
                                               reader.onload = (event) => {
                                                   try {
                                                       const obj = JSON.parse(event.target.result);
                                                       const yamlStr = yaml.dump(obj.yaml);
                                                       const phenomenon = obj.phenomenon;
                                                       setImportYaml(yamlStr);
                                                       setImportPhenomenon(phenomenon);
                                                       setShowImportModal(true);
                                                       fileInput.current.value = '';
                                                   } catch (e) {
                                                       setToast({
                                                           show: true,
                                                           msg: t('orchestration.incorrect_content'),
                                                           type: 'error'
                                                       })
                                                   }
                                               }
                                               reader.readAsText(file);
                                           }
                                       }
                                   }}
                                   className={"hidden"}
                            />

                            <button onClick={handleAddNew}
                                    className={`p-2 px-3 flex items-center gap-1.5 rounded-xl transition-all group shrink-0 shadow-sm ${isDark ? 'bg-indigo-500/20 text-indigo-400 hover:bg-indigo-500/30 border border-indigo-500/30' : 'bg-blue-600 hover:bg-blue-600 hover:text-white'}`}
                                    title={"Add New Workflow"}
                            >
                                <Plus size={16} className={"group-hover:rotate-90 transition-transform shrink-0"}/>
                                <span className={"text-xs font-bold whitespace-nowrap uppercase tracking-wider"}>
                                    Graph
                                </span>
                            </button>
                        </div>
                    </div>

                    <div className={"relative group"}>
                        <input type={"text"}
                               placeholder={t('orchestration.search', 'Search...')}
                               className={"w-full pl-10 pr-4 py-3 bg-zinc-50 dark:bg-zinc-800 border border-zinc-100 dark:border-zinc-700 rounded-xl text-sm font-bold outline-none dark:text-white focus:ring-4 focus:ring-blue-500/10 transition-all placeholder:font-medium"}
                               value={searchTerm}
                               onChange={(e) => setSearchTerm(e.target.value)}
                        />
                        <Search size={16}
                                className={"absolute left-3.5 top-3.5 text-zinc-400 group-focus-within:text-blue-500 transition-colors"}/>
                    </div>
                </div>

                <div className={"flex-1 overflow-y-auto space-y-3 custom-scrollbar min-h-0 pr-2"}>
                    {loading ? (
                        <div className={"flex flex-col items-center justify-center h-40 opacity-50"}>
                            <Loader2 className={"animate-spin text-blue-600 mb-2"} size={24}/>
                            <span className={"text-xs font-bold text-zinc-400"}>LOADING DATA...</span>
                        </div>
                    ) : workflows.length === 0 ? (
                        <div className={"text-center py-10 text-zinc-400 text-sm font-bold flex flex-col items-center"}>
                            <FileWarning size={32} className={'mb-2 opacity-50'}/>
                            No workflows found
                        </div>
                    ) : filteredWorkflows.length === 0 ? (
                        <div className={"text-center py-10 text-zinc-400 text-sm font-bold"}>
                            No result for "{searchTerm}"
                        </div>
                    ) : (
                        filteredWorkflows.map(wf => {
                            const isSelected = selectedId === wf.id;
                            return (
                                <div key={wf.id}
                                     onClick={() => handleSelectWorkflow(wf.id)}
                                     className={`group p-5 rounded-2xl border transition-all duration-300 cursor-pointer relative overflow-hidden ${isSelected ? 'bg-zinc-100 dark:bg-zinc-800 border-transparent shadow-inner' : 'border-zinc-100 dark:border-zinc-800 bg-white dark:bg-zinc-900 opacity-60 hover:opacity-100'}`}
                                >
                                    {isSelected && (
                                        <div
                                            className={"absolute left-0 top-0 bottom-0 w-1.5 bg-blue-600 animate-pulse"}/>
                                    )}
                                    <div className={"flex items-center justify-between mb-2 pl-2"}>
                                        <div
                                            className={`flex items-center gap-3 ${isSelected ? 'text-zinc-900 dark:text-white' : 'text-zinc-400'}`}>
                                            <Hash size={16}/>
                                            <h3 className={"font-black text-base uppercase leading-none truncate max-w-[230px]"}>
                                                {wf.name}
                                            </h3>
                                        </div>
                                    </div>
                                    <div
                                        className={`pl-8 text-[13px] font-black uppercase truncate max-w-[230px] ${isSelected ? 'text-blue-600 dark:text-blue-400' : 'text-zinc-400'}`}>
                                        {wf.keyword || 'NO KEYWORD'} {wf.confirmed && `· CONFIRMED`}
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>
            </div>
            <div className={"flex-1 min-w-0 flex flex-col min-h-0 relative"}>
                <div
                    className={"flex-1 bg-white dark:bg-zinc-900 rounded-[3rem] border border-zinc-200 dark:border-zinc-800 shadow-2xl relative overflow-hidden"}>
                    <WorkflowEditor isDark={isDark} visible={isAdding} onCancel={() => setIsAdding(false)}
                                    importedNodes={nodes} importedEdges={edges}/>
                    <div className={"absolute inset-0 flex flex-col"}>
                        <div
                            className={"p-8 border-b border-zinc-100 dark:border-zinc-800 flex justify-between items-center bg-zinc-50/50 dark:bg-zinc-900/50 backdrop-blur-sm shrink-0"}>
                            <div className={"flex items-center gap-6 min-w-0"}>
                                <div
                                    className={"p-4 rounded-2xl bg-gradient-to-br from-blue-600 to-blue-700 text-white shadow-lg shadow-blue-500/20"}>
                                    <Layout size={24}/>
                                </div>
                                <div className={"min-w-0"}>
                                    <h2 className={"text-xl font-black dark:text-white uppercase leading-none truncate max-w-[600px]"}>
                                        {currentWf?.name || 'No selection'}
                                    </h2>
                                    <div className={"flex items-c gap-2 mt-2"}>
                                        <span
                                            className={"text-[10px] font-bold bg-zinc-100 dark:bg-zinc-800 text-zinc-500 px-2 py-0.5 rounded-full uppercase tracking-wider"}>
                                            Topology & Config
                                        </span>
                                        {currentWf?.id && <span
                                            className={"text-[10px] font-mono text-zinc-300"}>ID:{currentWf.id}</span>}
                                    </div>
                                </div>
                            </div>
                            <button onClick={() => {
                                yamlToJson(yamlString, currentWf?.name)
                            }}
                                    className={`ml-2 px-4 py-1.5 text-sm font-bold rounded-xl shadow-lg transition-all active:scale-95 flex items-center gap-1 ${theme.primaryBtn}`}>
                                <svg className={"w-4 h-4"} fill={"none"} viewBox={"0 0 24 24"} stroke={"currentColor"}>
                                    <path strokeLinecap={"round"} strokeLinejoin={"round"} strokeWidth={2}
                                          d={"M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4v4"}/>
                                </svg>
                                {t('workflow.exportWorkflow')}
                            </button>
                        </div>

                        <div className={'flex-1 flex min-h-0 bg-zinc-50/30 dark:bg-zinc-950/30'}>
                            {currentWf ? (
                                <>
                                    <div className={"w-2/5 relative flex flex-col p-6 bg-white dark:bg-zinc-950"}>
                                        <div
                                            className={"absolute top-8 left-10 z-10 flex items-center gap-6 select-none"}>
                                            <div onClick={() => setRightPanelMode('yaml')}
                                                 className={`flex items-center gap-2 cursor-pointer transition-all text-[12px] uppercase tracking-widest ${rightPanelMode === 'yaml' ? 'font-black text-blue-600 scale-105' : 'font-bold text-zinc-300 hover:text-zinc-500'}`}
                                            >
                                                <FileText size={12}/>
                                                Workflow YAML
                                            </div>
                                            <div className={"h-3 w-[1px] bg-zinc-200 dark:bg-zinc-800"}></div>
                                            <div onClick={() => setRightPanelMode('trajectory')}
                                                 className={`flex items-center gap-2 cursor-pointer transition-all text-[12px] uppercase tracking-widest ${rightPanelMode === 'trajectory' ? 'font-black text-blue-600 scale-105' : 'font-bold text-zinc-300 hover:text-zinc-500'}`}
                                            >
                                                <Activity size={12}/>
                                                Human Procedure
                                            </div>
                                        </div>
                                        <textarea readOnly
                                                  value={rightPanelMode === 'yaml' ? yamlString : (currentWf.trajectory || 'No trajectory data available')}
                                                  className={"flex-1 bg-zinc-50 dark:bg-zinc-950 rounded-[2rem] border border-zinc-100 dark:border-zinc-800 p-8 pt-16 text-[16px] font-mono font-medium leading-relaxed text-zinc-600 dark:text-zinc-300 outline-none resize-none shadow-inner custom-scrollbar"}
                                        />
                                    </div>
                                    <div
                                        className={"w-3/5 border-r border-zinc-200 dark:border-zinc-800 relative flex flex-col p-6"}>
                                        <div
                                            className={"absolute top-8 left-10 text-[12px] font-black text-blue-500 uppercase tracking-widest z-10 pointer-events-none opacity-50"}>
                                            Workflow
                                        </div>
                                        <div
                                            className={"flex-1 bg-white dark:bg-zinc-900 rounded-[2rem] overflow-hidden border border-zinc-200 dark:border-zinc-800 shadow-sm relative"}>
                                            <WorkflowViewer isLoading={false} nodes={nodes} edges={edges}
                                                            isDark={isDark}/>
                                        </div>
                                    </div>
                                </>
                            ) : (
                                <div
                                    className={"w-full h-full flex flex-col items-center justify-center text-zinc-300 gap-4"}>
                                    <div className={"p-6 bg-zinc-50 dark:bg-zinc-800 rounded-full"}>
                                        <Layout size={40} className={"opacity-20"}/>
                                    </div>
                                    <p className={"font-bold uppercase tracking-widest text-xs opacity-50"}>Select a
                                        workflow to view details</p>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>

            {showImportModal && createPortal(ImportModal, document.body)}

            {toast.show && createPortal(
                <div
                    className={"fixed top-10 left-1/2 -translate-x-1/2 z-[10000] animate-in slide-in-from-top-4 fade-in duration-300"}>
                    <div className={`flex items-center gap-3 px-6 py-4 rounded-2xl shadow-2xl border transition-all ${
                        toast.type === 'success'
                            ? (isDark ? 'bg-zinc-900 border-emerald-500/30 text-emerald-400 ring-1 ring-emerald-500/20' : 'bg-white border-emerald-100 text-emerald-600 ring-1 ring-emerald-200')
                            : (isDark ? 'bg-zinc-900 border-rose-500/30 text-rose-400 ring-1 ring-rose-500/20' : 'bg-white border-red-100 text-red-600 ring-1 ring-red-200')}`}>
                        <div
                            className={`p-1.5 rounded-full ${toast.type === 'success' ? (isDark ? 'bg-emerald-500/20' : 'bg-emerald-50') : (isDark ? 'bg-rose-500/20' : 'bg-red-50')}`}>
                            {toast.type==='success' ? (
                                <svg className={"w-5 h-5"} fill={"none"} viewBox={"0 0 24 24"} stroke={"currentColor"}>
                                    <path strokeLinecap={"round"} strokeLinejoin={"round"} strokeWidth={3}
                                          d={"M5 13l4 4L19 7"}/>
                                </svg>
                            ) :(
                                <svg className={"w-5 h-5"} fill={"none"} viewBox={"0 0 24 24"} stroke={"currentColor"}>
                                    <path strokeLinecap={"round"} strokeLinejoin={"round"} strokeWidth={3}
                                          d={"M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.102 3 1.732 3z"}/>
                                </svg>
                            )}
                        </div>
                        <span className={"font-bold text-sm tracking-wide"}>{toast.msg}</span>
                        <button onClick={()=> setToast({...toast, show: false})} className={"ml-4 opacity-50 hover:opacity-100 transition-opacity"}>
                            <svg className={"w-4 h-4"} fill={"none"} viewBox={"0 0 24 24"} stroke={"currentColor"}>
                                <path strokeLinecap={"round"} strokeLinejoin={"round"} strokeWidth={3}
                                      d={"M6 18L18 6M6 6l12 12"}/>
                            </svg>
                        </button>
                    </div>
                </div>
                , document.body)}
        </div>
    )

}

export default OrchestrationCenter;