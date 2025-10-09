import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Button from "../../components/button";
import Input from "../../components/input";
import Modal from "../../components/modal";
import { authService, ApiError } from '../../services/auth';

export default function SignUp() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
      setError('Please fill in all fields');
      return;
    }

    if (password.length < 8) {
      setError('Password must be at least 8 characters long');
      return;
    }

    setIsLoading(true);
    setError(null);

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
        setError(err.message);
      } else {
        setError('An unexpected error occurred. Please try again.');
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
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}
          
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
    </div>
  );
}