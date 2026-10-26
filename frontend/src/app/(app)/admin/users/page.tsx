"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { ErrorState, PageHeader } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useMe } from "@/hooks/use-auth";
import { api, ApiError } from "@/lib/api";
import type { Page, Role, User } from "@/lib/types";
import { capitalize, formatDateTime } from "@/lib/utils";

const ROLES: Role[] = ["admin", "analyst", "viewer"];

export default function UsersPage() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const users = useQuery({
    queryKey: ["users", "all"],
    queryFn: () => api.get<Page<User>>("/users", { page_size: 100 }),
  });

  const update = useMutation({
    mutationFn: ({ id, ...body }: { id: string; role?: Role; is_active?: boolean }) =>
      api.patch<User>(`/users/${id}`, body),
    onSuccess: (u) => {
      qc.invalidateQueries({ queryKey: ["users"] });
      toast.success(`Updated ${u.full_name}`);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.displayMessage : "Update failed"),
  });

  return (
    <>
      <PageHeader
        title="Users"
        description="Grant analyst access to people who investigate incidents. New sign-ups start as viewers."
      />
      <div className="rounded-lg border bg-panel">
        {users.error ? (
          <div className="p-4">
            <ErrorState error={users.error} onRetry={() => users.refetch()} />
          </div>
        ) : users.isPending ? (
          <div className="flex flex-col gap-2 p-4" aria-busy>
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead className="hidden md:table-cell">Email</TableHead>
                <TableHead className="w-40">Role</TableHead>
                <TableHead className="hidden w-44 lg:table-cell">Last sign-in</TableHead>
                <TableHead className="w-32 text-right">Access</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.data.items.map((u) => {
                const isSelf = u.id === me?.id;
                return (
                  <TableRow key={u.id} className={u.is_active ? undefined : "opacity-60"}>
                    <TableCell className="font-medium">
                      {u.full_name}
                      {isSelf && <span className="ml-2 text-sm font-normal text-muted-foreground">(you)</span>}
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground md:table-cell">{u.email}</TableCell>
                    <TableCell>
                      <Select
                        value={u.role}
                        disabled={isSelf || update.isPending}
                        onValueChange={(role) => update.mutate({ id: u.id, role: role as Role })}
                      >
                        <SelectTrigger aria-label={`Role for ${u.full_name}`} className="h-8">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ROLES.map((r) => (
                            <SelectItem key={r} value={r}>
                              {capitalize(r)}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell className="hidden text-muted-foreground lg:table-cell">
                      {formatDateTime(u.last_login_at)}
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={isSelf || update.isPending}
                        onClick={() => update.mutate({ id: u.id, is_active: !u.is_active })}
                      >
                        {u.is_active ? "Deactivate" : "Reactivate"}
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </div>
    </>
  );
}
