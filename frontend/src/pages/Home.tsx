import { useState, useEffect } from "react";
import DatePicker from "react-datepicker";
import Input from "../components/input";
import Notification from "../components/notification";
import { ApiError } from "../services/move";
import goButton from "../../assets/go-button.svg";
import locationIcon from "../../assets/location.svg";
import calendarIcon from "../../assets/calendar.svg";
import AddressAutocomplete from "../components/address/AddressAutoComplete";
import { ChecklistCard } from "../components/chatcard";

const Field = ({
  icon,
  children,
}: {
  icon: string;
  children: React.ReactNode;
}) => (
  <div className="flex items-center gap-2 px-3">
    <img src={icon} alt="" className="w-4 h-4 opacity-80" />
    {children}
  </div>
);

export default function Home() {
  const [form, setForm] = useState({
    from_address: "",
    to_address: "",
    move_out_date: "",
    move_in_date: "",
  });

  const [notification, setNotification] = useState({
    show: false,
    message: "",
    type: "success" as "success" | "error",
  });
  const [isLoading, setIsLoading] = useState(false);
  const [checklistCards, setChecklistCards] = useState<any[]>([]);

  // --- Fetch checklists on page load ---
  useEffect(() => {
    const fetchChecklists = async () => {
      try {
        const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/checklists`);
        if (!res.ok) throw new Error("Failed to fetch checklists");
        const data = await res.json();
        setChecklistCards(data.checklists || []);
      } catch (err) {
        console.error("Error loading checklists:", err);
      }
    };

    fetchChecklists();
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleDateChange = (date: Date | null, fieldName: string) => {
    if (!date) {
      setForm((prev) => ({ ...prev, [fieldName]: "" }));
      return;
    }

    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    const value = `${year}-${month}-${day}`;

    setForm((prev) => ({ ...prev, [fieldName]: value }));
  };

  const parseLocalDate = (dateString: string): Date | undefined => {
    if (!dateString) return undefined;
    const [year, month, day] = dateString.split("-").map(Number);
    return new Date(year, month - 1, day);
  };

  const handleSubmit = async () => {
    const { from_address, to_address, move_out_date, move_in_date } = form;
    if (!from_address || !to_address || !move_out_date || !move_in_date) {
      setNotification({
        show: true,
        message: "Please fill in all fields.",
        type: "error",
      });
      return;
    }

    const token = localStorage.getItem("id_token");
    if (!token) {
      setNotification({
        show: true,
        message: "Please sign in first.",
        type: "error",
      });
      return;
    }

    setIsLoading(true);
    try {
      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/move`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(form),
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new ApiError(errBody.detail || "Failed to submit move.");
      }
      const result = await res.json();
      setNotification({
        show: true,
        message: result.message || "Move submitted successfully!",
        type: "success",
      });
    } catch (err) {
      const message =
        err instanceof ApiError ? err.message : "Failed to submit move.";
      setNotification({ show: true, message, type: "error" });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white text-sm flex flex-col items-center">
      {/* 🟧 Orange section (background only) */}
      <div className="bg-[#FF4124] h-[250px] flex justify-center items-end absolute top-15 left-0 right-0">
        {/* Floating bar overlaps bottom of orange */}
        <div className="bg-white shadow-md rounded-full border border-gray-200 px-6 py-3 flex flex-wrap md:flex-nowrap items-center justify-center gap-3 max-w-5xl w-full -mb-8.5 z-10">
          <Field icon={locationIcon}>
            <AddressAutocomplete
              name="from_address"
              placeholder="From Address"
              value={form.from_address}
              onChange={handleChange}
              onAddressSelect={(address) =>
                setForm((prev) => ({ ...prev, from_address: address }))
              }
              border={false}
            />
          </Field>

          <div className="w-px h-10 bg-gray-300" />

          <Field icon={calendarIcon}>
            <div className="w-full min-w-[160px]">
              <DatePicker
                selected={parseLocalDate(form.move_out_date)}
                onChange={(date) => handleDateChange(date, "move_out_date")}
                placeholderText="Move Out Date"
                dateFormat="MM/dd/yyyy"
                showMonthDropdown
                showYearDropdown
                dropdownMode="select"
                isClearable
                maxDate={parseLocalDate(form.move_in_date)}
                className="text-gray-700 bg-white rounded-full transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-[#FF4124] hover:border-[#FF4124] placeholder:text-gray-400 text-sm px-4 py-2 w-full"
              />
            </div>
          </Field>

          <div className="w-px h-10 bg-gray-300" />

          <Field icon={locationIcon}>
            <AddressAutocomplete
              name="to_address"
              placeholder="To Address"
              value={form.to_address}
              onChange={handleChange}
              onAddressSelect={(address) =>
                setForm((prev) => ({ ...prev, to_address: address }))
              }
              border={false}
            />
          </Field>

          <div className="w-px h-10 bg-gray-300" />

          <Field icon={calendarIcon}>
            <div className="w-full min-w-[160px]">
              <DatePicker
                selected={parseLocalDate(form.move_in_date)}
                onChange={(date) => handleDateChange(date, "move_in_date")}
                placeholderText="Move In Date"
                dateFormat="MM/dd/yyyy"
                showMonthDropdown
                showYearDropdown
                dropdownMode="select"
                isClearable
                minDate={parseLocalDate(form.move_out_date)}
                className="text-gray-700 bg-white rounded-full transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-[#FF4124] hover:border-[#FF4124] placeholder:text-gray-400 text-sm px-4 py-2 w-full"
              />
            </div>
          </Field>

          <div className="pl-2">
            <button
              onClick={handleSubmit}
              disabled={isLoading}
              className="flex items-center justify-center bg-[#FF4124] rounded-full w-10 h-10 hover:bg-[#000] hover:scale-105 transition focus:outline-none border-none"
            >
              <img src={goButton} alt="Submit" className="w-5 h-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Notification below */}
      <Notification
        message={notification.message}
        type={notification.type}
        isVisible={notification.show}
        onClose={() =>
          setNotification((prev) => ({ ...prev, show: false }))
        }
      />

      {/* 🔽 Checklist Cards */}
      {checklistCards.length > 0 && (
        <div className="w-full max-w-7xl px-6 py-10 mt-[320px] mb-12">
          <h2 className="text-lg font-semibold mb-15 pl-2 text-left">
            Previous Chats:
          </h2>
          <div className="flex flex-wrap gap-20 justify-center">
            {checklistCards.map((card) => (
              <ChecklistCard key={card.checklistId} {...card} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
