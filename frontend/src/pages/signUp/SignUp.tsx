import { useState } from "react";
import { useNavigate } from "react-router-dom";
import Button from "../../components/button";
import Input from "../../components/input";
import Modal from "../../components/modal";
import Notification from "../../components/notification";
import { authService, ApiError } from "../../services/auth";

export default function SignUp() {
  const [isLoading, setIsLoading] = useState(false);
  const [notification, setNotification] = useState<{
    show: boolean;
    message: string;
    type: "success" | "error";
  }>({ show: false, message: "", type: "error" });
  const navigate = useNavigate();

  // Sign up form fields
  const [username, setUsername] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [school, setSchool] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // Format phone number to E.164 format
  const formatPhoneToE164 = (phoneInput: string): string => {
    // Remove all non-digit characters
    const digitsOnly = phoneInput.replace(/\D/g, "");

    // Check if it's a valid US phone number (10 digits)
    if (digitsOnly.length === 10) {
      return `+1${digitsOnly}`;
    } else if (digitsOnly.length === 11 && digitsOnly.startsWith("1")) {
      return `+${digitsOnly}`;
    }

    return digitsOnly; // Return as-is if invalid, backend will handle error
  };

  // Validate phone number
  const isValidPhone = (phoneInput: string): boolean => {
    const digitsOnly = phoneInput.replace(/\D/g, "");
    return (
      digitsOnly.length === 10 ||
      (digitsOnly.length === 11 && digitsOnly.startsWith("1"))
    );
  };

  const handleSignUp = async () => {
    // Validate required fields
    if (!username || !firstName || !lastName || !phone || !email || !password) {
      setNotification({
        show: true,
        message: "Please fill in all required fields",
        type: "error",
      });
      return;
    }

    // Validate phone number
    if (!isValidPhone(phone)) {
      setNotification({
        show: true,
        message: "Please enter a valid 10-digit phone number",
        type: "error",
      });
      return;
    }

    // Validate password length
    if (password.length < 8) {
      setNotification({
        show: true,
        message: "Password must be at least 8 characters long",
        type: "error",
      });
      return;
    }

    setIsLoading(true);

    try {
      // Format phone to E.164 before sending
      const formattedPhone = formatPhoneToE164(phone);

      await authService.signUp({
        email,
        password,
        first_name: firstName,
        last_name: lastName,
        username,
        phone: formattedPhone,
      });

      navigate("/confirm-email", {
        state: { username, email },
      });
    } catch (err) {
      if (err instanceof ApiError) {
        setNotification({ show: true, message: err.message, type: "error" });
      } else {
        setNotification({
          show: true,
          message: "An unexpected error occurred. Please try again.",
          type: "error",
        });
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <h1
        className="text-5xl font-bold text-center mt-2"
        style={{ color: "#FF4124" }}
      >
        Sign Up
      </h1>
      <Modal isOpen={true} width={"500px"} mask={false} onClose={() => {}}>
        <div className="space-y-6">
          <div className="space-y-4">
            <Input
              placeholder="Username"
              name="username"
              width="350px"
              border={false}
              size={"lg"}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              disabled={isLoading}
            />
            <div className={"flex mx-5"}>
              <Input
                placeholder="First Name"
                name="firstName"
                width="162px"
                border={false}
                size={"lg"}
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                disabled={isLoading}
              />
              <Input
                placeholder="Last Name"
                name="lastName"
                width="162px"
                border={false}
                size={"lg"}
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                disabled={isLoading}
              />
            </div>
            <Input
              placeholder="School"
              name="school"
              width="350px"
              border={false}
              size={"lg"}
              value={school}
              onChange={(e) => setSchool(e.target.value)}
              disabled={isLoading}
            />
            <Input
              placeholder="Phone Number"
              name="phone"
              type="tel"
              width="350px"
              border={false}
              size={"lg"}
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              disabled={isLoading}
            />
            <Input
              placeholder="Email"
              name="email"
              type="email"
              width="350px"
              border={false}
              size={"lg"}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isLoading}
            />
            <Input
              placeholder="Password"
              name="password"
              type="password"
              width="350px"
              border={false}
              size={"lg"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isLoading}
            />
          </div>

          <div className="space-y-3">
            <div className="w-full">
              <Button
                text={isLoading ? "Signing Up..." : "Sign Up"}
                size={"lg"}
                color="#FF4124"
                onClick={handleSignUp}
              />
            </div>
            <div className="w-full">
              <Button
                text="Sign In"
                size={"lg"}
                onClick={() => navigate("/sign-in")}
              />
            </div>
          </div>
        </div>
      </Modal>

      <Notification
        message={notification.message}
        type={notification.type}
        isVisible={notification.show}
        onClose={() => setNotification((prev) => ({ ...prev, show: false }))}
      />
    </div>
  );
}
