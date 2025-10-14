import React, { useState, useEffect, useRef } from "react";
import { useDebouncedCallback } from "use-debounce";

interface AddressAutocompleteProps {
  name: string;
  placeholder: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onAddressSelect: (address: string) => void;
  border?: boolean;
}

interface Suggestion {
  place_id: number;
  display_name: string;
}

export default function AddressAutocomplete({
  name,
  placeholder,
  value,
  onChange,
  onAddressSelect,
  border = true,
}: AddressAutocompleteProps) {
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const justSelected = useRef(false);

  const fetchAddresses = useDebouncedCallback(async (query: string) => {
    if (query.length < 3) {
      setSuggestions([]);
      return;
    }

    try {
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(
          query
        )}&countrycodes=us&limit=5`,
        {
          headers: {
            "User-Agent": "YourAppName/1.0",
          },
        }
      );
      const data = await response.json();
      setSuggestions(data);
      setShowSuggestions(true);
    } catch (error) {
      console.error("Error fetching addresses:", error);
    }
  }, 500);

  useEffect(() => {
    if (justSelected.current) {
      justSelected.current = false;
      return;
    }
    
    if (value) {
      fetchAddresses(value);
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  }, [value, fetchAddresses]);

  const handleSuggestionClick = (address: string) => {
    justSelected.current = true;
    onAddressSelect(address);
    setShowSuggestions(false);
    setSuggestions([]);
  };

  const baseClasses = `
    text-gray-700 bg-white rounded-full
    transition-all duration-200 focus:outline-none
    focus:ring-2 focus:ring-[#FF4124] hover:border-[#FF4124]
    placeholder:text-gray-400 text-sm px-4 py-2 w-full
  `;

  const borderClasses = border
    ? "border border-gray-200 focus:border-[#FF4124]"
    : "";

  return (
    <div className="relative w-full">
      <input
        type="text"
        name={name}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        onFocus={() => {
          if (!justSelected.current && suggestions.length > 0) {
            setShowSuggestions(true);
          }
        }}
        onBlur={() => setTimeout(() => setShowSuggestions(false), 200)}
        className={`${baseClasses} ${borderClasses}`.trim()}
        autoComplete="off"
      />
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
          {suggestions.map((suggestion) => (
            <div
              key={suggestion.place_id}
              onClick={() => handleSuggestionClick(suggestion.display_name)}
              className="px-4 py-2 hover:bg-[#FF4124] hover:text-white cursor-pointer text-sm transition-colors"
            >
              {suggestion.display_name}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}