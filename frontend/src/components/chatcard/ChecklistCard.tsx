import locationIcon from "../../../assets/location.svg";
import calendarIcon from "../../../assets/calendar.svg";

type ChecklistItem = {
  title: string;
  status: string; // 'todo' | 'agentdone' | 'manualdone'
};

type ChecklistCardProps = {
  checklistId: string;
  createdAt: string;
  fromAddress: string;
  toAddress: string;
  moveOutDate: string;
  moveInDate: string;
  checklist: ChecklistItem[];
  onClick?: () => void;
  onDelete?: (id: string) => void;
};

export default function ChecklistCard({
  checklistId,
  createdAt,
  fromAddress,
  toAddress,
  moveOutDate,
  moveInDate,
  checklist,
  onClick,
  onDelete,
}: ChecklistCardProps) {
  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    const confirmDelete = confirm("Are you sure you want to delete this checklist?");
    if (!confirmDelete) return;

    try {
      const token = localStorage.getItem("id_token");
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/checklist/${checklistId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) throw new Error("Failed to delete checklist");
      if (onDelete) onDelete(checklistId);
      alert("Checklist deleted successfully.");
    } catch (err) {
      console.error("Error deleting checklist:", err);
      alert("Failed to delete checklist.");
    }
  };

  return (
    <div
      className="bg-white rounded-2xl shadow-md border border-gray-100 p-6 w-[340px] hover:scale-[1.02] transition relative cursor-pointer"
      onClick={onClick}
    >
      {/* Delete Button */}
      <button
        onClick={handleDelete}
        className="absolute top-3 right-3 text-gray-400 hover:text-red-500 transition"
        aria-label="Delete checklist"
      >
        ✕
      </button>

      {/* Header */}
      <h3 className="text-lg font-semibold text-center mb-4">
        Created:{" "}
        {new Date(createdAt).toLocaleDateString("en-US", {
          year: "numeric",
          month: "long",
          day: "numeric",
        })}
      </h3>

      {/* FROM */}
      <div className="mb-3 text-left">
        <p className="font-semibold text-sm mb-1">From:</p>
        <div className="flex items-start gap-2 text-xs text-gray-700 mb-1">
          <img src={locationIcon} className="w-3.5 h-3.5 mt-[2px]" />
          <p>{fromAddress}</p>
        </div>
        <div className="flex items-start gap-2 text-xs text-gray-700">
          <img src={calendarIcon} className="w-3.5 h-3.5 mt-[2px]" />
          <p>{new Date(moveOutDate).toLocaleDateString()}</p>
        </div>
      </div>

      {/* TO */}
      <div className="mb-4 text-left">
        <p className="font-semibold text-sm mb-1">To:</p>
        <div className="flex items-start gap-2 text-xs text-gray-700 mb-1">
          <img src={locationIcon} className="w-3.5 h-3.5 mt-[2px]" />
          <p>{toAddress}</p>
        </div>
        <div className="flex items-start gap-2 text-xs text-gray-700">
          <img src={calendarIcon} className="w-3.5 h-3.5 mt-[2px]" />
          <p>{new Date(moveInDate).toLocaleDateString()}</p>
        </div>
      </div>

      <div className="border-t border-gray-200 my-4"></div>

      {/* Checklist */}
      <div className="space-y-2 text-left">
        {checklist.map((item, index) => {
          const isAgentDone = item.status === "agentdone";
          const isManualDone = item.status === "manualdone"; 

          const checkColor = isAgentDone
            ? "text-blue-500"
            : isManualDone
            ? "text-red-500"
            : "text-gray-400";

          const strikeColor = isAgentDone
            ? "decoration-blue-500"
            : isManualDone
            ? "decoration-red-500"
            : "decoration-gray-400";

          return (
            <div
              key={index}
              className="flex items-center gap-3 bg-gray-50 rounded-full px-3 py-2"
            >
              {/* Checkbox */}
              <div
                className={`w-5 h-5 flex items-center justify-center rounded-md border ${
                  isAgentDone
                    ? "border-blue-500 bg-blue-50"
                    : isManualDone
                    ? "border-red-500 bg-red-50"
                    : "border-gray-300 bg-gray-100"
                }`}
              >
                {isAgentDone || isManualDone ? (
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className={`w-3.5 h-3.5 ${checkColor}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={3}
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                ) : (
                  <div className="w-2 h-2 rounded-sm bg-gray-300"></div>
                )}
              </div>

              {/* Task title */}
              <span
                className={`text-sm ${
                  isAgentDone || isManualDone
                    ? `line-through ${strikeColor} text-gray-400`
                    : "text-gray-700"
                }`}
              >
                {item.title}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
