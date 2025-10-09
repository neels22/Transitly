import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import Button from "../../components/button";
import Input from "../../components/input";
import Modal from "../../components/modal";
import { authService, ApiError } from '../../services/auth';

export default function ConfirmEmail() {
  const [confirmationCode, setConfirmationCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
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
      setError('Please enter the confirmation code');
      return;
    }

    setIsLoading(true);
    setError(null);

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
        setError(err.message);
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendCode = async () => {
    setIsLoading(true);
    setError(null);

    try {
      await authService.resendConfirmation({ username });
      setError('Confirmation code sent! Check your email.');
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Failed to resend confirmation code.');
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
          
          {error && (
            <div className={`border px-4 py-3 rounded-lg ${
              error.includes('sent') 
                ? 'bg-green-50 border-green-200 text-green-700'
                : 'bg-red-50 border-red-200 text-red-700'
            }`}>
              {error}
            </div>
          )}
          
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
    </div>
  );
}
