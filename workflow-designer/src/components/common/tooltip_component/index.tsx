// @ts-ignore
import React, { useState, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';

interface Props {
    children: React.ReactElement;
    content: string;
}

const Tooltip = ({ children, content }: Props) => {
    const [isOpen, setIsOpen] = useState(false);
    const [coords, setCoords] = useState({ top: 0, left: 0 });
    const triggerRef = useRef<HTMLDivElement>(null);

    const handleMouseEnter = () => {
        if (triggerRef.current) {
            const rect = triggerRef.current.getBoundingClientRect();
            setCoords({
                top: rect.top + window.scrollY,
                left: rect.right + 10,
            });
            setIsOpen(true);
        }
    };

    return (
        <>
            <div
                ref={triggerRef}
                onMouseEnter={handleMouseEnter}
                onMouseLeave={() => setIsOpen(false)}
                className="w-full"
            >
                {children}
            </div>

            {createPortal(
                <AnimatePresence>
                    {isOpen && (
                        <motion.div
                            initial={{ opacity: 0, x: -10 }}
                            animate={{ opacity: 1, x: 0 }}
                            exit={{ opacity: 0, x: -10 }}
                            style={{
                                position: 'absolute',
                                top: coords.top,
                                left: coords.left,
                                zIndex: 9999,
                            }}
                            className="pointer-events-none"
                        >
                            <div className="max-w-[340px] p-2.5 bg-gray-900/95 text-white text-sm rounded-lg shadow-2xl border border-gray-700 backdrop-blur-sm">
                                {content}
                                <div className="absolute top-4 -left-1 w-2 h-2 bg-gray-900 border-l border-b border-gray-700 rotate-45" />
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>,
                document.body
            )}
        </>
    );
};

export default Tooltip;