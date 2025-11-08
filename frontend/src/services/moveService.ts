import { makeRequest, ApiError } from "./http";

export const moveService = {
  submitMove: async (data: {
    from_address: string;
    to_address: string;
    move_out_date: string;
    move_in_date: string;
  }) => {
    const token = localStorage.getItem("id_token");

    return makeRequest("/move", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(data),
    });
  }
};

export { ApiError } from "./http";
