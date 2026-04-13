import { Handle, Position, useConnection } from "@xyflow/react";

export const StartNode = ({ selected }) => {
    const connection = useConnection();
    const isConnecting = connection.inProgress;

    const handleBaseStyle = `
        !w-[8px] !h-[8px] !bg-emerald-400 border-2 border-white 
        transition-all duration-300 ease-out cursor-crosshair
        hover:!w-[12px] hover:!h-[12px] hover:shadow-lg
        z-[110]
        
        /* 连线起点反馈 */
        [&.react-flow__handle-connecting]:ring-4 [&.react-flow__handle-connecting]:ring-emerald-500/20
        
        /* 隐形热区 */
        after:content-[''] after:absolute after:top-1/2 after:left-1/2 after:-translate-x-1/2 after:-translate-y-1/2 
        after:w-[30px] after:h-[30px] after:bg-transparent
    `;

    const targetHandleStyle = {
        position: 'absolute',
        width: '100%',
        height: '100%',
        top: 0,
        left: 0,
        transform: 'none',
        background: 'transparent',
        border: 'none',
        borderRadius: '50%',
        zIndex: isConnecting ? 100 : -1,
        pointerEvents: isConnecting ? 'auto' : 'none',
    };

    return (
        <div className={`
            w-16 h-16 rounded-full bg-emerald-500 shadow-lg border-4 border-white flex items-center justify-center text-white font-bold text-sm relative group transition-all
            ${selected ? 'ring-2 ring-emerald-500 ring-offset-2' : ''}
        `}>
            <div className={"absolute -top-8 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-[10px] px-2 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap"}>
                开始节点
            </div>
            START

            {/* Target Handle (Allows looping back or connecting TO start) */}
            <Handle type="target" position={Position.Top} id="target" style={targetHandleStyle} />

            <Handle type={"source"} position={Position.Top} id={"s-top"} style={{ left: '50%' }} className={handleBaseStyle} />
            <Handle type={"source"} position={Position.Bottom} id={"s-bottom"} style={{ left: '50%' }} className={handleBaseStyle} />
            <Handle type={"source"} position={Position.Left} id={"s-left"} style={{ top: '50%' }} className={handleBaseStyle} />
            <Handle type={"source"} position={Position.Right} id={"s-right"} style={{ top: '50%' }} className={handleBaseStyle} />
        </div>
    );
};

export const EndNode = ({ selected }) => {
    const connection = useConnection();
    const isConnecting = connection.inProgress;

    const handleBaseStyle = `
        !w-[8px] !h-[8px] !bg-rose-400 border-2 border-white 
        transition-all duration-300 ease-out cursor-crosshair
        hover:!w-[12px] hover:!h-[12px] hover:shadow-lg
        z-[110]
        
        /* 连线起点反馈 */
        [&.react-flow__handle-connecting]:ring-4 [&.react-flow__handle-connecting]:ring-rose-500/20
        
        /* 隐形热区 */
        after:content-[''] after:absolute after:top-1/2 after:left-1/2 after:-translate-x-1/2 after:-translate-y-1/2 
        after:w-[30px] after:h-[30px] after:bg-transparent
    `;

    const targetHandleStyle = {
        position: 'absolute',
        width: '100%',
        height: '100%',
        top: 0,
        left: 0,
        transform: 'none',
        background: 'transparent',
        border: 'none',
        borderRadius: '50%',
        zIndex: isConnecting ? 100 : -1,
        pointerEvents: isConnecting ? 'auto' : 'none',
    };

    return (
        <div className={`
            w-16 h-16 rounded-full bg-rose-500 shadow-lg border-4 border-white flex items-center justify-center text-white font-bold text-sm relative group transition-all
            ${selected ? 'ring-2 ring-rose-500 ring-offset-2' : ''}
        `}>
            <div className={"absolute -top-8 left-1/2 -translate-x-1/2 bg-slate-800 text-white text-[10px] px-2 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap"}>
                结束节点
            </div>
            END

            {/* Target Handle (Whole node target) */}
            <Handle type="target" position={Position.Top} id="target" style={targetHandleStyle} />

            {/* Source Handles (Optional, for completeness) */}
            <Handle type={"source"} position={Position.Top} id={"s-top"} style={{ left: '50%' }} className={handleBaseStyle} />
            <Handle type={"source"} position={Position.Bottom} id={"s-bottom"} style={{ left: '50%' }} className={handleBaseStyle} />
            <Handle type={"source"} position={Position.Left} id={"s-left"} style={{ top: '50%' }} className={handleBaseStyle} />
            <Handle type={"source"} position={Position.Right} id={"s-right"} style={{ top: '50%' }} className={handleBaseStyle} />
        </div>
    );
};