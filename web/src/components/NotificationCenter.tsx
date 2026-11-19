import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import type { OperatorNotification } from "../types";
import { EmptyState, ErrorNotice, SkeletonList } from "./Feedback";
import { Drawer } from "./ui/Drawer";
import { BellIcon } from "./ui/Icons";
import { api } from "../lib/api";
import { formatError, formatRelative, requestIdOf } from "../lib/format";
import { queryKeys } from "../lib/query";

const KIND_LABEL: Record<string, string> = {
  moderation_appeal: "Recurso",
  moderation_report: "Denúncia",
  moderation_action: "Medida",
  moderation_appeal_result: "Resultado",
};

function notificationTarget(item: OperatorNotification): string | null {
  const data = item.data ?? {};
  if (item.kind === "moderation_appeal") {
    const appealId = typeof data.appeal_id === "string" ? data.appeal_id : null;
    return appealId
      ? `/moderation?appeal=${encodeURIComponent(appealId)}#appeals`
      : "/moderation#appeals";
  }
  if (item.kind === "moderation_report") {
    const reportId = typeof data.report_id === "string" ? data.report_id : null;
    return reportId ? `/moderation?report=${encodeURIComponent(reportId)}` : "/moderation";
  }
  return null;
}

const PAGE_SIZE = 30;

export function NotificationCenter() {
  const [open, setOpen] = useState(false);
  const unreadQuery = useQuery({
    queryKey: queryKeys.moderationNotificationsUnread,
    queryFn: () => api.getModerationNotificationsUnreadCount(),
    refetchInterval: 60_000,
  });
  const unread = unreadQuery.data?.unread_count ?? 0;
  const label = unread > 0 ? `Notificações, ${unread} não lidas` : "Notificações";

  return (
    <>
      <button
        type="button"
        className="icon-button bell"
        aria-label={label}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen(true)}
      >
        <BellIcon size={18} />
        {unread > 0 ? (
          <span className="bell__badge" aria-hidden="true">
            {unread > 99 ? "99+" : unread}
          </span>
        ) : null}
      </button>
      <span className="sr-only" aria-live="polite">
        {unread > 0 ? `${unread} notificações não lidas` : ""}
      </span>
      {open ? <NotificationDrawer onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function NotificationDrawer({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [limit, setLimit] = useState(PAGE_SIZE);

  const listQuery = useQuery({
    queryKey: [...queryKeys.moderationNotifications(unreadOnly), limit],
    queryFn: () => api.listModerationNotifications({ unreadOnly, limit, offset: 0 }),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["moderation", "notifications"] });

  const markRead = useMutation({
    mutationFn: (notificationId: string) => api.markModerationNotificationRead(notificationId),
    onSuccess: () => void invalidate(),
  });

  const markAll = useMutation({
    mutationFn: () => api.markAllModerationNotificationsRead(),
    onSuccess: () => void invalidate(),
  });

  const items = listQuery.data?.notifications ?? [];
  const unread = listQuery.data?.unread_count ?? 0;
  const canLoadMore = items.length >= limit && limit < 100;

  function openItem(item: OperatorNotification) {
    if (!item.read_at) markRead.mutate(item.id);
    const target = notificationTarget(item);
    if (target) {
      onClose();
      navigate(target);
    }
  }

  return (
    <Drawer
      closeLabel="Fechar notificações"
      open
      onClose={onClose}
      title="Notificações"
      description="Avisos de moderação e da sua conta."
      footer={
        <div className="drawer__footer-row">
          <button
            type="button"
            className="button button--small button--ghost"
            onClick={() => markAll.mutate()}
            disabled={unread === 0 || markAll.isPending}
          >
            {markAll.isPending ? "Marcando..." : "Marcar todas como lidas"}
          </button>
          {canLoadMore ? (
            <button
              type="button"
              className="button button--small button--ghost"
              onClick={() => setLimit(limit + PAGE_SIZE)}
              disabled={listQuery.isFetching}
            >
              {listQuery.isFetching ? "Carregando..." : "Carregar mais"}
            </button>
          ) : null}
        </div>
      }
    >
      <div className="drawer__filters" role="group" aria-label="Filtrar notificações">
        <button
          type="button"
          className={unreadOnly ? "chip" : "chip chip--active"}
          aria-pressed={!unreadOnly}
          onClick={() => setUnreadOnly(false)}
        >
          Todas
        </button>
        <button
          type="button"
          className={unreadOnly ? "chip chip--active" : "chip"}
          aria-pressed={unreadOnly}
          onClick={() => setUnreadOnly(true)}
        >
          Não lidas
          {unread > 0 ? ` (${unread})` : ""}
        </button>
      </div>

      {listQuery.isPending ? (
        <SkeletonList rows={3} label="Carregando notificações..." />
      ) : listQuery.error ? (
        <ErrorNotice
          message={formatError(listQuery.error)}
          requestId={requestIdOf(listQuery.error)}
          onRetry={() => void listQuery.refetch()}
        />
      ) : items.length === 0 ? (
        <EmptyState
          title={unreadOnly ? "Nenhuma não lida" : "Nenhuma notificação"}
          icon={<BellIcon size={28} />}
        >
          {unreadOnly
            ? "Você já leu tudo por aqui."
            : "Avisos de moderação e de medidas aparecem nesta central."}
        </EmptyState>
      ) : (
        <ul className="notification-list">
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={
                  item.read_at ? "notification-item" : "notification-item notification-item--unread"
                }
                onClick={() => openItem(item)}
              >
                <span className="notification-item__top">
                  <span className="notification-item__kind">
                    {KIND_LABEL[item.kind] ?? item.kind}
                  </span>
                  <span className="notification-item__time">{formatRelative(item.created_at)}</span>
                </span>
                <span className="notification-item__title">{item.title}</span>
                <span className="notification-item__body">{item.body}</span>
                {!item.read_at ? <span className="sr-only">Não lida</span> : null}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Drawer>
  );
}
