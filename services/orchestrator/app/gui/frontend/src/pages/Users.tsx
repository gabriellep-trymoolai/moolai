import React, { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Search, Plus } from 'lucide-react';

export const Users: React.FC = () => {
  const [searchTerm, setSearchTerm] = useState('');

  const users = [
    {
      id: 1,
      name: 'Arun Krishnaswamy',
      email: 'admin@trymool.ai',
      interactions: 245,
      riskyBehavior: 21,
      satisfaction: 87,
      responseTime: '82ms',
      role: 'User',
      status: 'Online',
      lastActive: '2 mins ago'
    },
    {
      id: 2,
      name: 'Arun Krishnaswamy',
      email: 'admin@trymool.ai',
      interactions: 245,
      riskyBehavior: 21,
      satisfaction: 87,
      responseTime: '82ms',
      role: 'User',
      status: 'Online',
      lastActive: '2 mins ago'
    },
    {
      id: 3,
      name: 'Arun Krishnaswamy',
      email: 'admin@trymool.ai',
      interactions: 245,
      riskyBehavior: 21,
      satisfaction: 87,
      responseTime: '82ms',
      role: 'User',
      status: 'Online',
      lastActive: '2 mins ago'
    },
    {
      id: 4,
      name: 'Arun Krishnaswamy',
      email: 'admin@trymool.ai',
      interactions: 245,
      riskyBehavior: 21,
      satisfaction: 87,
      responseTime: '82ms',
      role: 'User',
      status: 'Online',
      lastActive: '2 mins ago'
    },
    {
      id: 5,
      name: 'Arun Krishnaswamy',
      email: 'admin@trymool.ai',
      interactions: 245,
      riskyBehavior: 21,
      satisfaction: 87,
      responseTime: '82ms',
      role: 'User',
      status: 'Online',
      lastActive: '2 mins ago'
    },
    {
      id: 6,
      name: 'Arun Krishnaswamy',
      email: 'admin@trymool.ai',
      interactions: 245,
      riskyBehavior: 21,
      satisfaction: 87,
      responseTime: '82ms',
      role: 'User',
      status: 'Online',
      lastActive: '2 mins ago'
    }
  ];

  return (
    <div className="flex-1 p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-foreground">User Management</h1>
        <Button className="bg-orange-primary hover:bg-orange-dark text-white">
          <Plus className="h-4 w-4 mr-2" />
          Add User
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="p-6">
          <div className="space-y-2">
            <h3 className="text-sm text-muted-foreground">Total Users</h3>
            <div className="flex items-center gap-2">
              <span className="text-3xl font-bold text-foreground">6</span>
              <span className="text-sm text-green-400">+0% from yesterday</span>
            </div>
          </div>
        </Card>
        
        <Card className="p-6">
          <div className="space-y-2">
            <h3 className="text-sm text-muted-foreground">Active Users Today</h3>
            <div className="flex items-center gap-2">
              <span className="text-3xl font-bold text-foreground">6</span>
              <span className="text-sm text-green-400">+13% from yesterday</span>
            </div>
          </div>
        </Card>

        <Card className="p-6">
          <div className="space-y-2">
            <h3 className="text-sm text-muted-foreground">Avg. Session Duration</h3>
            <div className="flex items-center gap-2">
              <span className="text-3xl font-bold text-foreground">45 min</span>
              <span className="text-sm text-red-400">-15.3% from last month</span>
            </div>
          </div>
        </Card>
      </div>

      {/* All Users Section */}
      <div className="space-y-4">
        <div>
          <h2 className="text-lg font-semibold text-foreground">All Users</h2>
          <p className="text-sm text-muted-foreground">Manage the users of your organization logged into the system</p>
        </div>

        {/* Search */}
        <div className="flex gap-3">
          <div className="flex-1 relative max-w-md">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10"
            />
          </div>
        </div>

        {/* Table */}
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr className="border-b border-border">
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">USER</th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">ROLE</th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">STATUS</th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">LAST ACTIVE</th>
                  <th className="text-left p-4 text-sm font-medium text-muted-foreground">ACTIONS</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className="border-b border-border hover:bg-muted/30">
                    <td className="p-4">
                      <div className="space-y-1">
                        <div className="text-sm font-medium text-foreground">{user.name}</div>
                        <div className="text-xs text-muted-foreground">{user.email}</div>
                      </div>
                    </td>
                    <td className="p-4">
                      <span className="text-sm text-foreground">{user.role}</span>
                    </td>
                    <td className="p-4">
                      <Badge variant="outline" className="border-green-500 text-green-400">
                        <div className="w-2 h-2 bg-green-500 rounded-full mr-2"></div>
                        {user.status}
                      </Badge>
                    </td>
                    <td className="p-4">
                      <span className="text-sm text-foreground">{user.lastActive}</span>
                    </td>
                    <td className="p-4">
                      <span className="text-sm text-orange-primary cursor-pointer hover:underline">
                        Manage User
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center justify-between p-4 border-t border-border">
            <span className="text-sm text-muted-foreground">1-10 of 97</span>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">Rows per page: 10</span>
              <div className="flex gap-1">
                <Button variant="ghost" size="sm" className="h-8 w-8 p-0">‹</Button>
                <span className="text-sm text-muted-foreground">1/10</span>
                <Button variant="ghost" size="sm" className="h-8 w-8 p-0">›</Button>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};