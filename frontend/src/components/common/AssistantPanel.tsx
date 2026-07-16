import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Bot, Send, Sparkles, X, MessageSquare } from "lucide-react";
import { api } from "@/lib/api";
import type { AssistantMessage } from "@/lib/types";
import { GlassCard } from "@/components/common/GlassCard";
import { GlowButton } from "@/components/common/GlowButton";
import { cn } from "@/lib/utils";

const defaultChips = [
  "Camera not working",
  "Enable Browser Guard",
  "Explain high risk",
  "Download report",
  "Secondary camera help",
  "Database offline mode",
];

interface Props {
  embedded?: boolean;
  defaultOpen?: boolean;
}

export function AssistantPanel({ embedded, defaultOpen }: Props) {
  const [open, setOpen] = useState(!!defaultOpen || !!embedded);
  const [mode, setMode] = useState<"student" | "instructor" | "admin">("student");
  const [messages, setMessages] = useState<AssistantMessage[]>([
    {
      id: "m0",
      role: "assistant",
      content:
        "Hi, I'm ProctorAI Guide. I help with platform setup, monitoring, and reviewing sessions — I can't help with exam content. What do you need?",
      timestamp: new Date().toISOString(),
      quick_actions: defaultChips,
    },
  ]);
  const [input, setInput] = useState("");
  const [pending, setPending] = useState(false);

  const send = async (text: string) => {
    if (!text.trim()) return;
    const userMsg: AssistantMessage = {
      id: `m_${Date.now()}`,
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages((m) => [...m, userMsg]);
    setInput("");
    setPending(true);
    try {
      const res = await api.assistantQuery({ query: text, mode });
      const reply: AssistantMessage = {
        id: `a_${Date.now()}`,
        role: "assistant",
        content: res.reply,
        timestamp: new Date().toISOString(),
        quick_actions: res.quick_actions,
        confidence: res.confidence,
        intent: res.intent,
        references: res.references,
      };
      setMessages((m) => [...m, reply]);
    } finally {
      setPending(false);
    }
  };

  if (!embedded) {
    return (
      <>
        {!open && (
          <button
            onClick={() => setOpen(true)}
            className="fixed bottom-6 right-6 z-40 inline-flex items-center gap-2 rounded-full bg-gradient-primary px-4 py-3 text-sm font-medium text-primary-foreground shadow-glow hover:brightness-110"
          >
            <Bot className="h-4 w-4" /> Guide
          </button>
        )}
        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ x: 480, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 480, opacity: 0 }}
              transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
              className="fixed bottom-6 right-6 top-20 z-40 flex w-[380px] max-w-[calc(100vw-2rem)] flex-col"
            >
              <PanelBody
                onClose={() => setOpen(false)}
                mode={mode}
                setMode={setMode}
                messages={messages}
                pending={pending}
                send={send}
                input={input}
                setInput={setInput}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <PanelBody
        mode={mode}
        setMode={setMode}
        messages={messages}
        pending={pending}
        send={send}
        input={input}
        setInput={setInput}
      />
    </div>
  );
}

function PanelBody({
  onClose,
  mode,
  setMode,
  messages,
  pending,
  send,
  input,
  setInput,
}: {
  onClose?: () => void;
  mode: "student" | "instructor" | "admin";
  setMode: (m: "student" | "instructor" | "admin") => void;
  messages: AssistantMessage[];
  pending: boolean;
  send: (s: string) => void;
  input: string;
  setInput: (s: string) => void;
}) {
  return (
    <GlassCard strong className="flex h-full flex-col p-0">
      <div className="flex items-center gap-2 border-b border-white/10 p-3">
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-primary text-primary-foreground">
          <Bot className="h-4 w-4" />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold">ProctorAI Guide</div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
            Support only · won't answer exam questions
          </div>
        </div>
        <div className="ml-auto flex items-center gap-1">
          {(["student", "instructor", "admin"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={cn(
                "rounded-md px-2 py-1 text-[10px] uppercase tracking-wider transition-colors",
                mode === m
                  ? "bg-primary/20 text-primary"
                  : "text-muted-foreground hover:bg-white/5",
              )}
            >
              {m}
            </button>
          ))}
          {onClose && (
            <button
              onClick={onClose}
              className="ml-1 rounded-md p-1 text-muted-foreground hover:bg-white/10"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto p-3">
        {messages.map((m) => (
          <Bubble key={m.id} msg={m} onChip={send} />
        ))}
        {pending && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5 text-primary" />
            <span className="flex gap-1">
              <Dot /> <Dot delay={0.15} /> <Dot delay={0.3} />
            </span>
          </div>
        )}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="flex items-center gap-2 border-t border-white/10 p-3"
      >
        <MessageSquare className="h-4 w-4 text-muted-foreground" />
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about ProctorAI..."
          className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        />
        <GlowButton type="submit" size="sm" disabled={!input.trim() || pending}>
          <Send className="h-4 w-4" />
        </GlowButton>
      </form>
    </GlassCard>
  );
}

function Dot({ delay = 0 }: { delay?: number }) {
  return (
    <motion.span
      animate={{ opacity: [0.2, 1, 0.2] }}
      transition={{ duration: 1, repeat: Infinity, delay }}
      className="h-1.5 w-1.5 rounded-full bg-primary"
    />
  );
}

function Bubble({ msg, onChip }: { msg: AssistantMessage; onChip: (s: string) => void }) {
  const isUser = msg.role === "user";
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className={cn("flex flex-col gap-2", isUser ? "items-end" : "items-start")}
    >
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-3 py-2 text-sm",
          isUser
            ? "bg-gradient-primary text-primary-foreground"
            : "whitespace-pre-line border border-white/10 bg-white/5 text-foreground",
        )}
      >
        {msg.content}
      </div>
      {msg.quick_actions && msg.quick_actions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {msg.quick_actions.map((q) => (
            <button
              key={q}
              onClick={() => onChip(q)}
              className="rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 text-[11px] text-primary transition-colors hover:bg-primary/20"
            >
              {q}
            </button>
          ))}
        </div>
      )}
    </motion.div>
  );
}
