export default function Tabs({ tabs, activeTab, setActiveTab }) {
  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {tabs.map((tab) => (
        <button
          key={tab}
          onClick={() => setActiveTab(tab)}
          className={`px-4 py-2 rounded-xl text-sm font-medium transition ${
            activeTab === tab
              ? "bg-slate-900 text-white"
              : "bg-slate-200 text-slate-700 hover:bg-slate-300"
          }`}
        >
          {tab}
        </button>
      ))}
    </div>
  );
}