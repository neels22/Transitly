import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import Button from "../../components/button";
import Input from "../../components/input";
import Modal from "../../components/modal";
import Notification from "../../components/notification";
import { authService, ApiError } from '../../services/auth';

export default function ConfirmEmail() {
  const [confirmationCode, setConfirmationCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [notification, setNotification] = useState<{
    show: boolean;
    message: string;
    type: 'success' | 'error';
  }>({ show: false, message: '', type: 'error' });
  const navigate = useNavigate();
  const location = useLocation();
  
  // Get user data from navigation state
  const { username, email } = location.state || {};

  useEffect(() => {
    // Redirect to signup if no user data is provided
    if (!username || !email) {
      navigate('/sign-up');
    }
  }, [username, email, navigate]);

  const handleConfirmSignUp = async () => {
    if (!confirmationCode) {
      setNotification({ show: true, message: 'Please enter the confirmation code', type: 'error' });
      return;
    }

    setIsLoading(true);

    try {
      await authService.confirmSignUp({
        username,
        code: confirmationCode,
      });
      
      // Redirect to sign in page with success message
      navigate('/sign-in', { 
        state: { 
          message: 'Email confirmed successfully! You can now sign in.' 
        } 
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

  const handleResendCode = async () => {
    setIsLoading(true);

    try {
      await authService.resendConfirmation({ username });
      setNotification({ show: true, message: 'Confirmation code sent! Check your email.', type: 'success' });
    } catch (err) {
      if (err instanceof ApiError) {
        setNotification({ show: true, message: err.message, type: 'error' });
      } else {
        setNotification({ show: true, message: 'Failed to resend confirmation code.', type: 'error' });
      }
    } finally {
      setIsLoading(false);
    }
  };

  if (!username || !email) {
    return null; // Will redirect in useEffect
  }

  return (
    <div>
      <h1 className="text-5xl font-bold text-center mt-2" style={{ color: "#FF4124" }}>
        Confirm Email
      </h1>
      <Modal
        isOpen={true}
        width={"500px"}
        mask={false}
        onClose={() => {}}
      >
        <div className="space-y-6">
          <div className="text-center">
            <p className="text-gray-600 mb-4">
              We've sent a confirmation code to <strong>{email}</strong>
            </p>
            <p className="text-gray-500 text-sm">
              Please check your email and enter the confirmation code below.
            </p>
          </div>
          
          
          <div className="space-y-4">
            <Input
              placeholder="Enter confirmation code"
              width="350px"
              border={false}
              size={"lg"}
              value={confirmationCode}
              onChange={(e) => setConfirmationCode(e.target.value)}
              disabled={isLoading}
            />
          </div>

          <div className="space-y-3">
            <div className="w-full">
              <Button
                text={isLoading ? "Confirming..." : "Confirm"}
                size={"lg"}
                color="#FF4124"
                onClick={handleConfirmSignUp}
              />
            </div>
            <div className="w-full">
              <Button
                text={isLoading ? "Sending..." : "Resend Code"}
                onClick={handleResendCode}
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
