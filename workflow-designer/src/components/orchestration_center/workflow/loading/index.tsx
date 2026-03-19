// @ts-ignore
import React from 'react';

interface WorkflowLoaderProps {
    isDark?: boolean;
    message?: string;
    subMessage?: string;
    className?: string;
}

const WorkflowLoader: React.FC<WorkflowLoaderProps> = ({
                                                           isDark = true,
                                                           loadingMessage = "Loading Workflow",
                                                           subMessage = "正在初始化数据...",
                                                           className = ""
                                                       }) => {
    return (
        <div className={`
      relative w-full h-full min-h-[400px] flex flex-col items-center justify-center transition-colors duration-500
      ${isDark ? 'bg-[#0b0e14] text-slate-200' : 'bg-slate-50 text-slate-600'}
      ${className}
    `}>
            <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <div className={`absolute -top-[10%] -left-[10%] w-[40%] h-[40%] rounded-full blur-[120px] opacity-20 
          ${isDark ? 'bg-blue-900' : 'bg-blue-200'}`}
                />
            </div>

            <div className="relative flex flex-col items-center z-10">
                <div className="relative w-12 h-12 mb-6">
                    <div className={`absolute inset-0 rounded-full border-[3px] opacity-20 
            ${isDark ? 'border-slate-700' : 'border-slate-300'}`}
                    />
                    <div className="absolute inset-0 rounded-full border-[3px] border-transparent border-t-blue-500 border-r-blue-500/30 animate-spin" />
                    <div className={`absolute inset-2 rounded-full animate-pulse 
            ${isDark ? 'bg-slate-800' : 'bg-slate-200'}`}
                    />
                </div>

                <div className="flex flex-col items-center gap-1">
                    <p className={`text-sm font-medium tracking-widest  animate-pulse
            ${isDark ? 'text-slate-300' : 'text-slate-600'}`}>
                        {loadingMessage}
                    </p>
                    <div className="h-[2px] w-8 rounded-full bg-blue-500 transition-all duration-1000 animate-bounce mt-1" />
                    <p className={`text-xs mt-2 opacity-60 font-light
            ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
                        {subMessage}
                    </p>
                </div>
            </div>
        </div>
    );
};

export default WorkflowLoader;