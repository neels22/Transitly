import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from "../../components/button";
import Input from "../../components/input";
import Modal from "../../components/modal";
import Notification from "../../components/notification";
import { authService, ApiError } from '../../services/auth';

export default function SignUp() {
  const [isLoading, setIsLoading] = useState(false);
  const [notification, setNotification] = useState<{
    show: boolean;
    message: string;
    type: 'success' | 'error';
  }>({ show: false, message: '', type: 'error' });
  const navigate = useNavigate();
  
  // Sign up form fields
  const [username, setUsername] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [school, setSchool] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleSignUp = async () => {
    if (!username || !firstName || !lastName || !email || !password) {
      setNotification({ show: true, message: 'Please fill in all fields', type: 'error' });
      return;
    }

    if (password.length < 8) {
      setNotification({ show: true, message: 'Password must be at least 8 characters long', type: 'error' });
      return;
    }

    setIsLoading(true);

    try {
      await authService.signUp({
        email,
        password,
        first_name: firstName,
        last_name: lastName,
        username,
      });
      
      navigate('/confirm-email', {
        state: { username, email }
      });
    } catch (err) {
      if (err instanceof ApiError) {
        setNotification({ show: true, message: err.message, type: 'error' });
      } else {
        setNotification({ show: true, message: 'An unexpected error occurred. Please try again.', type: 'error' });
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      <h1 className="text-5xl font-bold text-center mt-2" style={{ color: "#FF4124" }}>Sign Up</h1>
      <Modal
        isOpen={true}
        width={"500px"}
        mask={false}
        onClose={() => {}}
      >
        <div className="space-y-6">
          
          <div className="space-y-4">
            <Input
              placeholder="Username"
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
                width="162px"
                border={false}
                size={"lg"}
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                disabled={isLoading}
              />
              <Input
                placeholder="Last Name"
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
              width="350px"
              border={false}
              size={"lg"}
              value={school}
              onChange={(e) => setSchool(e.target.value)}
              disabled={isLoading}
            />
            <Input
              placeholder="Email"
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
                onClick={() => navigate('/sign-in')}
              />
            </div>
          </div>
        </div>
      </Modal>
      
      <Notification
        message={notification.message}
        type={notification.type}
        isVisible={notification.show}
        onClose={() => setNotification(prev => ({ ...prev, show: false }))}
      />
    </div>
  );
}