import React, { useState, useEffect } from 'react';
import type { UserData, ListingData } from '../../types';

export interface ListingProps {
  data: ListingData;
}


async function getUser(userId: string): Promise<UserData | null> {
  // TODO: Implement actual API call when backend is ready
  return null;
}

export default function Listing({ data }: ListingProps) {
  const [userData, setUserData] = useState<UserData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchUser = async () => {
      try {
        const user = await getUser(data.userId);
        setUserData(user);
      } catch (error) {
        console.error('Error fetching user:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchUser();
  }, [data.userId]);

  return (
    <div className="bg-white " style={{ width: '455px', height: '320px' }}>
      <div className="relative z-10" style={{ height: '232px' }}>
        <img
          src={data.photos[0]}
          alt={data.description}
          className="w-full h-full object-cover rounded-2xl"
        />
      </div>

      <div className="bg-gray-100 px-4 py-4 rounded-b-2xl -translate-y-2">
        <div className="flex items-center justify-between">
          <div className="text-2xl font-bold text-gray-900">
            ${data.price.toFixed(2)}
          </div>

          <div className="flex items-center space-x-3">
            {loading ? (
              <div className="w-10 h-10 rounded-full bg-gray-200 animate-pulse"></div>
            ) : (
              <img
                src={userData?.profilePicture || 'https://via.placeholder.com/40'}
                alt={userData?.displayName || 'User'}
                className="w-10 h-10 rounded-full object-cover border-2 border-white shadow-sm"
              />
            )}
            <div className="text-right">
              <div className="font-bold text-gray-900 text-sm">
                {loading ? (
                  <div className="w-20 h-4 bg-gray-200 animate-pulse rounded"></div>
                ) : (
                  userData?.displayName || 'Unknown User'
                )}
              </div>
              <div className="text-sm text-gray-600">
                {data.location}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
