import { useState } from 'react';
import api from '../api/client';
import { Send, Bot, User } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// The Copilot's answers are real markdown (GFM tables included) from the
// LLM - previously rendered as a raw pre-wrapped string, so a response with
// a table showed literal "| col | col |" pipe characters instead of an
// actual table. These overrides style react-markdown's output to match the
// app's dark theme instead of using its unstyled defaults.
const markdownComponents = {
  h1: (p) => <h3 className="text-cyan-400 font-bold text-base mt-4 mb-2 first:mt-0" {...p} />,
  h2: (p) => <h3 className="text-cyan-400 font-bold text-base mt-4 mb-2 first:mt-0" {...p} />,
  h3: (p) => <h4 className="text-cyan-400 font-semibold text-sm mt-3 mb-1 first:mt-0" {...p} />,
  p: (p) => <p className="mb-2 last:mb-0 leading-relaxed" {...p} />,
  strong: (p) => <strong className="text-white font-semibold" {...p} />,
  ul: (p) => <ul className="list-disc list-inside space-y-1 mb-2" {...p} />,
  ol: (p) => <ol className="list-decimal list-inside space-y-1 mb-2" {...p} />,
  li: (p) => <li className="text-slate-200" {...p} />,
  code: (p) => <code className="bg-dark-900 text-cyan-300 px-1.5 py-0.5 rounded text-xs" {...p} />,
  table: (p) => (
    <div className="overflow-x-auto my-3 rounded-lg border border-dark-700">
      <table className="w-full text-xs border-collapse" {...p} />
    </div>
  ),
  thead: (p) => <thead className="bg-dark-700" {...p} />,
  th: (p) => <th className="px-3 py-2 text-left font-semibold text-slate-300 border-b border-dark-700" {...p} />,
  td: (p) => <td className="px-3 py-2 text-slate-200 border-b border-dark-700/50 align-top" {...p} />,
  tr: (p) => <tr className="even:bg-dark-900/40" {...p} />,
  hr: () => <hr className="border-dark-700/60 my-3" />,
};

function MessageContent({ text }) {
  return (
    <div className="text-sm">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {text}
      </ReactMarkdown>
    </div>
  );
}

export default function Copilot() {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'Hello Investigator. I am the NEXUS-X Intelligence Copilot. How can I assist you with the case graph today?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMsg = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setLoading(true);

    try {
      const res = await api.post('/api/copilot/query', { query: userMsg });
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: res.data.answer,
        evidence: res.data.evidence,
        confidence: res.data.confidence
      }]);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setMessages(prev => [...prev, {
        role: 'assistant',
        text: typeof detail === 'string' ? detail : 'Error connecting to intelligence service.'
      }]);
    }
    setLoading(false);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)]">
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-white">Investigation Copilot</h1>
        <p className="text-slate-400">AI-assisted natural language graph querying</p>
      </div>

      <div className="flex-1 glass-panel flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`flex max-w-[80%] ${msg.role === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${msg.role === 'user' ? 'bg-primary-500 ml-3' : 'bg-dark-700 mr-3'}`}>
                  {msg.role === 'user' ? <User className="w-5 h-5 text-white" /> : <Bot className="w-5 h-5 text-primary-400" />}
                </div>
                <div className={`p-4 rounded-xl text-sm ${msg.role === 'user' ? 'bg-primary-500 text-white' : 'bg-dark-800 text-slate-200 border border-dark-700'}`}>
                  {msg.role === 'assistant' ? (
                    <MessageContent text={msg.text} />
                  ) : (
                    <div className="whitespace-pre-wrap text-sm">{msg.text}</div>
                  )}
                  {msg.evidence && (
                    <div className="mt-4 pt-3 border-t border-dark-700/50">
                      <div className="text-xs font-semibold text-primary-400 mb-1">Evidence Sources:</div>
                      <ul className="text-xs text-slate-400 list-disc list-inside">
                        {msg.evidence.map((ev, idx) => <li key={idx}>{ev}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="flex">
                <div className="w-8 h-8 rounded-full bg-dark-700 flex items-center justify-center mr-3">
                  <Bot className="w-5 h-5 text-primary-400 animate-pulse" />
                </div>
                <div className="p-4 rounded-xl bg-dark-800 border border-dark-700">
                  <div className="flex space-x-2">
                    <div className="w-2 h-2 bg-slate-500 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{animationDelay: '0.2s'}}></div>
                    <div className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{animationDelay: '0.4s'}}></div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="p-4 border-t border-dark-700 bg-dark-900/50">
          <form onSubmit={handleSend} className="flex gap-2">
            <input 
              type="text" 
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Ask about connections, priorities, or node importance..."
              className="flex-1 bg-dark-800 border border-dark-700 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-primary-500 transition-colors"
            />
            <button 
              type="submit"
              disabled={loading}
              className="bg-primary-500 hover:bg-primary-600 disabled:opacity-50 text-white px-4 py-3 rounded-lg transition-colors"
            >
              <Send className="w-5 h-5" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
