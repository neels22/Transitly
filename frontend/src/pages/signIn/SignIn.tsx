import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import Button from "../../components/button";
import Input from "../../components/input";
import Modal from "../../components/modal";
import Notification from "../../components/notification";
import { useUser } from "../../context/user.tsx";
import { authService, ApiError } from '../../services/auth';


export default function SignIn() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [notification, setNotification] = useState<{
    show: boolean;
    message: string;
    type: 'success' | 'error';
  }>({ show: false, message: '', type: 'success' });
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    // Check for success message from confirmation page
    if (location.state?.message) {
      setNotification({ show: true, message: location.state.message, type: 'success' });
      // Clear the location state
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [location.state, navigate, location.pathname]);

  const { setUser, setTokens } = useUser();

  const handleSignIn = async () => {
    if (!email || !password) {
      setNotification({ show: true, message: 'Please enter both email and password', type: 'error' });
      return;
    }

    setIsLoading(true);

    try {
      const response = await authService.signIn({
        email,
        password,
      });
      
      // Set user and tokens in context
      setUser(response.user);
      setTokens(response.tokens);
      
      // Navigate to home page
      navigate('/');
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.message.includes('not confirmed')) {
          setNotification({ show: true, message: 'Please confirm your email address before signing in.', type: 'error' });
        } else {
          setNotification({ show: true, message: err.message, type: 'error' });
        }
      } else {
        setNotification({ show: true, message: 'An unexpected error occurred. Please try again.', type: 'error' });
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSignUp = () => {
    navigate('/sign-up');
  };

  /*const handleForgotPassword = () => {
    // TODO: Implement forgot password flow
    setError('Forgot password feature coming soon!');
  };*/

  return (
    <div>
      <h1 className="text-5xl font-bold text-center mt-34" style={{ color: "#FF4124" }}>Sign In</h1>
      <Modal
        isOpen={true}
        width={"500px"}
        mask={false}
        onClose={() => {}}
      >
        <div className="space-y-6">
          
          <div className="space-y-4">
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
                text={isLoading ? "Signing In..." : "Sign In"}
                size={"lg"}
                onClick={handleSignIn}
              />
            </div>
            <div className="w-full">
              <Button
                text="Sign Up"
                size={"lg"}
                color="#FF4124"
                onClick={handleSignUp}
              />
            </div>
            {/*<div className="w-full">
              <Button
                text="Forgot Password?"
                size={"lg"}
                onClick={handleForgotPassword}
              />
            </div>*/}
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
