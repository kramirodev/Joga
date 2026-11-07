import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";

import { AppHeader } from "../components/AppHeader";
import { EmptyState, ErrorNotice, LoadingBlock } from "../components/Feedback";
import { api } from "../lib/api";
import { formatDate, formatError, requestIdOf, roleLabel } from "../lib/format";
import { queryKeys } from "../lib/query";
import type { VenueAvailability, VenueBlackout, VenuePhoto, VenueSpace } from "../types";

const WEEKDAYS = [
  { value: 1, label: "Segunda" },
  { value: 2, label: "Terça" },
  { value: 3, label: "Quarta" },
  { value: 4, label: "Quinta" },
  { value: 5, label: "Sexta" },
  { value: 6, label: "Sábado" },
  { value: 7, label: "Domingo" },
];

function money(cents: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(cents / 100);
}

function weekdayLabel(value: number): string {
  return WEEKDAYS.find((item) => item.value === value)?.label ?? String(value);
}

function PhotoThumb({ photo }: { photo: VenuePhoto }) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    void api
      .fetchPhoto(photo.content_url)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [photo.content_url]);

  if (failed) return <div className="photo-thumb photo-thumb--empty">Falha ao carregar</div>;
  if (!url) return <div className="photo-thumb photo-thumb--empty">Carregando...</div>;
  return <img className="photo-thumb" src={url} alt={photo.caption ?? "Foto da quadra"} />;
}

function PhotoStatus({ photo }: { photo: VenuePhoto }) {
  const labels: Record<VenuePhoto["status"], string> = {
    PENDING: "Em revisão",
    APPROVED: "Aprovada",
    REJECTED: "Rejeitada",
    REMOVED: "Removida",
  };
  return (
    <span className={`badge badge--${photo.status.toLowerCase()}`}>{labels[photo.status]}</span>
  );
}

export function VenuePage() {
  const { organizationId = "", venueId = "" } = useParams<{
    organizationId: string;
    venueId: string;
  }>();
  const queryClient = useQueryClient();
  const [tab, setTab] = useState<"spaces" | "photos">("spaces");
  const [selectedSpaceIdState, setSelectedSpaceId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);

  const [spaceName, setSpaceName] = useState("");
  const [spaceDescription, setSpaceDescription] = useState("");
  const [sportDraft, setSportDraft] = useState<{ spaceId: string; ids: string[] } | null>(null);
  const [weekday, setWeekday] = useState(1);
  const [startTime, setStartTime] = useState("18:00");
  const [endTime, setEndTime] = useState("22:00");
  const [price, setPrice] = useState("120");
  const [slotMinutes, setSlotMinutes] = useState(60);
  const [blackoutStart, setBlackoutStart] = useState("");
  const [blackoutEnd, setBlackoutEnd] = useState("");
  const [blackoutReason, setBlackoutReason] = useState("");
  const [blackoutReference, setBlackoutReference] = useState("");
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoCaption, setPhotoCaption] = useState("");
  const [photoSpaceId, setPhotoSpaceId] = useState("");

  const organizationQuery = useQuery({
    queryKey: queryKeys.organization(organizationId),
    queryFn: () => api.getOrganization(organizationId),
    enabled: organizationId.length > 0,
  });
  const venueQuery = useQuery({
    queryKey: queryKeys.venue(organizationId, venueId),
    queryFn: () => api.getVenue(organizationId, venueId),
    enabled: organizationId.length > 0 && venueId.length > 0,
  });
  const spacesQuery = useQuery({
    queryKey: queryKeys.spaces(organizationId, venueId),
    queryFn: async () => (await api.listSpaces(organizationId, venueId)).spaces,
    enabled: organizationId.length > 0 && venueId.length > 0,
  });
  const sportsQuery = useQuery({
    queryKey: queryKeys.sports,
    queryFn: async () => (await api.listSports()).sports,
  });
  const photosQuery = useQuery({
    queryKey: queryKeys.photos(organizationId, venueId),
    queryFn: () => api.listPhotos(organizationId, venueId),
    enabled: organizationId.length > 0 && venueId.length > 0,
  });

  const spaces = useMemo(() => spacesQuery.data ?? [], [spacesQuery.data]);
  const selectedSpaceId = selectedSpaceIdState ?? spaces[0]?.id ?? null;
  const selectedSpace = spaces.find((space) => space.id === selectedSpaceId) ?? null;
  const sportIds =
    sportDraft && sportDraft.spaceId === selectedSpace?.id
      ? sportDraft.ids
      : (selectedSpace?.sports.map((sport) => sport.id) ?? []);

  const availabilityQuery = useQuery({
    queryKey: queryKeys.availability(organizationId, venueId, selectedSpaceId ?? ""),
    queryFn: async () =>
      (await api.listAvailability(organizationId, venueId, selectedSpaceId ?? "")).availability,
    enabled: Boolean(selectedSpaceId),
  });
  const blackoutsQuery = useQuery({
    queryKey: queryKeys.blackouts(organizationId, venueId, selectedSpaceId ?? ""),
    queryFn: async () =>
      (await api.listBlackouts(organizationId, venueId, selectedSpaceId ?? "")).blackouts,
    enabled: Boolean(selectedSpaceId),
  });

  const loading =
    organizationQuery.isPending ||
    venueQuery.isPending ||
    spacesQuery.isPending ||
    sportsQuery.isPending;
  const queryError =
    organizationQuery.error ??
    venueQuery.error ??
    spacesQuery.error ??
    sportsQuery.error ??
    photosQuery.error;

  function invalidateSpaces() {
    void queryClient.invalidateQueries({ queryKey: queryKeys.spaces(organizationId, venueId) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.audit(organizationId) });
  }

  function invalidatePhotos() {
    void queryClient.invalidateQueries({ queryKey: queryKeys.photos(organizationId, venueId) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.audit(organizationId) });
  }

  function invalidateSchedule() {
    if (!selectedSpaceId) return;
    void queryClient.invalidateQueries({
      queryKey: queryKeys.availability(organizationId, venueId, selectedSpaceId),
    });
    void queryClient.invalidateQueries({
      queryKey: queryKeys.blackouts(organizationId, venueId, selectedSpaceId),
    });
    void queryClient.invalidateQueries({ queryKey: queryKeys.audit(organizationId) });
  }

  const createSpaceMutation = useMutation({
    mutationFn: () =>
      api.createSpace(organizationId, venueId, {
        name: spaceName,
        description: spaceDescription.trim() || null,
      }),
    onSuccess: (space) => {
      setSpaceName("");
      setSpaceDescription("");
      setSelectedSpaceId(space.id);
      setNotice("Quadra criada. Agora defina modalidades e agenda.");
      invalidateSpaces();
    },
    onError: (caught) => {
      setNotice(null);
      setActionError(caught);
    },
  });

  const deleteSpaceMutation = useMutation({
    mutationFn: (space: VenueSpace) => api.deleteSpace(organizationId, venueId, space.id),
    onSuccess: (_data, space) => {
      if (selectedSpaceId === space.id) setSelectedSpaceId(null);
      setNotice("Quadra removida.");
      invalidateSpaces();
    },
    onError: (caught) => {
      setNotice(null);
      setActionError(caught);
    },
  });

  const sportsMutation = useMutation({
    mutationFn: () =>
      api.replaceSpaceSports(organizationId, venueId, selectedSpaceId ?? "", sportIds),
    onSuccess: () => {
      setSportDraft(null);
      setNotice("Modalidades atualizadas.");
      invalidateSpaces();
    },
    onError: (caught) => {
      setNotice(null);
      setActionError(caught);
    },
  });

  const availabilityMutation = useMutation({
    mutationFn: () =>
      api.createAvailability(organizationId, venueId, selectedSpaceId ?? "", {
        weekday,
        start_time: `${startTime}:00`,
        end_time: `${endTime}:00`,
        price_cents: Math.round(Number(price.replace(",", ".")) * 100),
        slot_minutes: slotMinutes,
      }),
    onSuccess: () => {
      setNotice("Janela de agenda criada.");
      invalidateSchedule();
    },
    onError: (caught) => {
      setNotice(null);
      setActionError(caught);
    },
  });

  const deleteAvailabilityMutation = useMutation({
    mutationFn: (item: VenueAvailability) =>
      api.deleteAvailability(organizationId, venueId, item.space_id, item.id),
    onSuccess: () => {
      setNotice("Janela removida.");
      invalidateSchedule();
    },
    onError: (caught) => {
      setNotice(null);
      setActionError(caught);
    },
  });

  const blackoutMutation = useMutation({
    mutationFn: () =>
      api.createBlackout(organizationId, venueId, selectedSpaceId ?? "", {
        starts_at: new Date(blackoutStart).toISOString(),
        ends_at: new Date(blackoutEnd).toISOString(),
        reason: blackoutReason,
        external_reference: blackoutReference.trim() || null,
      }),
    onSuccess: () => {
      setBlackoutStart("");
      setBlackoutEnd("");
      setBlackoutReason("");
      setBlackoutReference("");
      setNotice("Bloqueio criado.");
      invalidateSchedule();
    },
    onError: (caught) => {
      setNotice(null);
      setActionError(caught);
    },
  });

  const deleteBlackoutMutation = useMutation({
    mutationFn: (item: VenueBlackout) =>
      api.deleteBlackout(organizationId, venueId, item.space_id, item.id),
    onSuccess: () => {
      setNotice("Bloqueio removido.");
      invalidateSchedule();
    },
    onError: (caught) => {
      setNotice(null);
      setActionError(caught);
    },
  });

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!photoFile) throw new Error("Selecione uma foto.");
      return api.uploadPhoto(organizationId, venueId, {
        file: photoFile,
        caption: photoCaption.trim() || undefined,
        spaceId: photoSpaceId || undefined,
      });
    },
    onSuccess: () => {
      setPhotoFile(null);
      setPhotoCaption("");
      setNotice("Foto enviada para revisão.");
      invalidatePhotos();
    },
    onError: (caught) => {
      setNotice(null);
      setActionError(caught);
    },
  });

  const reviewMutation = useMutation({
    mutationFn: ({
      photo,
      decision,
      reason,
    }: {
      photo: VenuePhoto;
      decision: "APPROVED" | "REJECTED";
      reason?: string;
    }) => api.reviewPhoto(organizationId, venueId, photo.id, decision, reason),
    onSuccess: () => {
      setNotice("Revisão registrada.");
      invalidatePhotos();
    },
    onError: (caught) => {
      setNotice(null);
      setActionError(caught);
    },
  });

  const removePhotoMutation = useMutation({
    mutationFn: (photo: VenuePhoto) => api.removePhoto(organizationId, venueId, photo.id),
    onSuccess: () => {
      setNotice("Foto removida.");
      invalidatePhotos();
    },
    onError: (caught) => {
      setNotice(null);
      setActionError(caught);
    },
  });

  if (loading) {
    return (
      <div className="app-shell">
        <AppHeader />
        <main className="page">
          <LoadingBlock label="Carregando quadras..." />
        </main>
      </div>
    );
  }

  if (queryError || !organizationQuery.data || !venueQuery.data) {
    return (
      <div className="app-shell">
        <AppHeader />
        <main className="page">
          <ErrorNotice
            message={queryError ? formatError(queryError) : "Estabelecimento não encontrado."}
            requestId={requestIdOf(queryError)}
          />
          <Link className="button button--link" to={`/organizations/${organizationId}`}>
            Voltar para a organização
          </Link>
        </main>
      </div>
    );
  }

  const organization = organizationQuery.data;
  const venue = venueQuery.data;
  const photos = photosQuery.data?.photos ?? [];
  const canReview = photosQuery.data?.can_review ?? false;
  const busy =
    createSpaceMutation.isPending ||
    deleteSpaceMutation.isPending ||
    sportsMutation.isPending ||
    availabilityMutation.isPending ||
    blackoutMutation.isPending ||
    uploadMutation.isPending ||
    reviewMutation.isPending ||
    removePhotoMutation.isPending;

  function createSpace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    createSpaceMutation.mutate();
  }

  function saveSports() {
    if (selectedSpaceId) sportsMutation.mutate();
  }

  function createAvailability(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSpaceId) return;
    availabilityMutation.mutate();
  }

  function createBlackout(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedSpaceId || !blackoutStart || !blackoutEnd) return;
    blackoutMutation.mutate();
  }

  function uploadPhoto(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    uploadMutation.mutate();
  }

  function reviewPhoto(photo: VenuePhoto, decision: "APPROVED" | "REJECTED") {
    let reason: string | undefined;
    if (decision === "REJECTED") {
      const answer = window.prompt("Motivo da rejeição (obrigatório):");
      if (!answer) return;
      reason = answer;
    }
    reviewMutation.mutate({ photo, decision, reason });
  }

  return (
    <div className="app-shell">
      <AppHeader subtitle={venue.name} />
      <main className="page">
        <nav className="breadcrumb" aria-label="Navegação">
          <Link to="/">Organizações</Link>
          <span aria-hidden="true">/</span>
          <Link to={`/organizations/${organizationId}`}>{organization.name}</Link>
          <span aria-hidden="true">/</span>
          <span>{venue.name}</span>
        </nav>

        <section className="page-heading">
          <div>
            <p className="eyebrow">{roleLabel(organization.role)}</p>
            <h1>{venue.name}</h1>
            <p className="muted">
              {[venue.city, venue.state].filter(Boolean).join(" · ") || "Local não informado"} ·{" "}
              {venue.timezone}
            </p>
          </div>
        </section>

        {notice ? (
          <div className="notice notice--success" role="status" aria-live="polite">
            {notice}
          </div>
        ) : null}
        {actionError ? (
          <ErrorNotice message={formatError(actionError)} requestId={requestIdOf(actionError)} />
        ) : null}

        <div className="tabs" role="tablist" aria-label="Seções do estabelecimento">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "spaces"}
            className={tab === "spaces" ? "tab tab--active" : "tab"}
            onClick={() => setTab("spaces")}
          >
            Quadras <span className="tab__count">{spaces.length}</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "photos"}
            className={tab === "photos" ? "tab tab--active" : "tab"}
            onClick={() => setTab("photos")}
          >
            Fotos <span className="tab__count">{photos.length}</span>
          </button>
        </div>

        {tab === "spaces" ? (
          <section className="grid grid--sidebar">
            <div className="stack">
              <div className="card">
                <h2>Quadras e espaços</h2>
                {spaces.length === 0 ? (
                  <EmptyState title="Nenhuma quadra cadastrada">
                    Cadastre a primeira quadra ao lado para abrir a agenda.
                  </EmptyState>
                ) : (
                  <ul className="space-list">
                    {spaces.map((space) => (
                      <li key={space.id}>
                        <button
                          type="button"
                          className={
                            space.id === selectedSpaceId
                              ? "space-card space-card--active"
                              : "space-card"
                          }
                          onClick={() => setSelectedSpaceId(space.id)}
                        >
                          <span>
                            <strong>{space.name}</strong>
                            <small>
                              {space.sports.map((sport) => sport.name).join(" · ") ||
                                "Sem modalidade"}
                            </small>
                          </span>
                          <span className="badge badge--muted">{space.status}</span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}

                <form className="form form--inline" onSubmit={createSpace}>
                  <h3>Nova quadra</h3>
                  <label className="field">
                    <span>Nome</span>
                    <input
                      type="text"
                      value={spaceName}
                      onChange={(event) => setSpaceName(event.target.value)}
                      minLength={1}
                      maxLength={120}
                      placeholder="Ex.: Quadra 1"
                      required
                    />
                  </label>
                  <label className="field">
                    <span>Descrição</span>
                    <input
                      type="text"
                      value={spaceDescription}
                      onChange={(event) => setSpaceDescription(event.target.value)}
                      maxLength={280}
                      placeholder="Coberta, piso sintético..."
                    />
                  </label>
                  <button type="submit" className="button button--primary" disabled={busy}>
                    Cadastrar quadra
                  </button>
                </form>
              </div>
            </div>

            <div className="stack">
              {!selectedSpace ? (
                <div className="card">
                  <EmptyState title="Selecione uma quadra">
                    Escolha uma quadra para editar modalidades, agenda e bloqueios.
                  </EmptyState>
                </div>
              ) : (
                <>
                  <div className="card">
                    <div className="section-heading">
                      <div>
                        <h2>{selectedSpace.name}</h2>
                        <p className="muted">{selectedSpace.description || "Sem descrição."}</p>
                      </div>
                      <button
                        type="button"
                        className="button button--small button--danger"
                        disabled={busy}
                        onClick={() => {
                          if (
                            window.confirm(`Remover a quadra "${selectedSpace.name}" e sua agenda?`)
                          ) {
                            deleteSpaceMutation.mutate(selectedSpace);
                          }
                        }}
                      >
                        Remover quadra
                      </button>
                    </div>

                    <h3>Modalidades</h3>
                    <div className="checkbox-grid">
                      {(sportsQuery.data ?? []).map((sport) => (
                        <label key={sport.id} className="checkbox">
                          <input
                            type="checkbox"
                            checked={sportIds.includes(sport.id)}
                            onChange={(event) => {
                              if (!selectedSpaceId) return;
                              setSportDraft({
                                spaceId: selectedSpaceId,
                                ids: event.target.checked
                                  ? [...sportIds, sport.id]
                                  : sportIds.filter((id) => id !== sport.id),
                              });
                            }}
                          />
                          <span>{sport.name}</span>
                        </label>
                      ))}
                    </div>
                    <button
                      type="button"
                      className="button button--primary"
                      onClick={saveSports}
                      disabled={busy}
                    >
                      Salvar modalidades
                    </button>
                  </div>

                  <div className="card">
                    <h2>Agenda semanal</h2>
                    {availabilityQuery.isPending ? (
                      <LoadingBlock label="Carregando agenda..." />
                    ) : (availabilityQuery.data ?? []).length === 0 ? (
                      <EmptyState title="Nenhuma janela">
                        Defina horários e preços para esta quadra.
                      </EmptyState>
                    ) : (
                      <ul className="schedule-list">
                        {(availabilityQuery.data ?? []).map((item) => (
                          <li key={item.id} className="schedule-row">
                            <span>
                              <strong>{weekdayLabel(item.weekday)}</strong>
                              <small>
                                {item.start_time.slice(0, 5)}–{item.end_time.slice(0, 5)} ·{" "}
                                {money(item.price_cents)} · {item.slot_minutes} min
                              </small>
                            </span>
                            <button
                              type="button"
                              className="button button--small button--danger"
                              disabled={busy}
                              onClick={() => deleteAvailabilityMutation.mutate(item)}
                            >
                              Remover
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}

                    <form className="form form--inline" onSubmit={createAvailability}>
                      <h3>Nova janela</h3>
                      <div className="form-row">
                        <label className="field">
                          <span>Dia</span>
                          <select
                            value={weekday}
                            onChange={(event) => setWeekday(Number(event.target.value))}
                          >
                            {WEEKDAYS.map((item) => (
                              <option key={item.value} value={item.value}>
                                {item.label}
                              </option>
                            ))}
                          </select>
                        </label>
                        <label className="field">
                          <span>Início</span>
                          <input
                            type="time"
                            value={startTime}
                            onChange={(event) => setStartTime(event.target.value)}
                            required
                          />
                        </label>
                        <label className="field">
                          <span>Fim</span>
                          <input
                            type="time"
                            value={endTime}
                            onChange={(event) => setEndTime(event.target.value)}
                            required
                          />
                        </label>
                      </div>
                      <div className="form-row">
                        <label className="field">
                          <span>Preço (R$)</span>
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={price}
                            onChange={(event) => setPrice(event.target.value)}
                            required
                          />
                        </label>
                        <label className="field">
                          <span>Duração da vaga (min)</span>
                          <input
                            type="number"
                            min="15"
                            max="240"
                            value={slotMinutes}
                            onChange={(event) => setSlotMinutes(Number(event.target.value))}
                            required
                          />
                        </label>
                      </div>
                      <button type="submit" className="button button--primary" disabled={busy}>
                        Adicionar janela
                      </button>
                    </form>
                  </div>

                  <div className="card">
                    <h2>Bloqueios e reservas externas</h2>
                    {blackoutsQuery.isPending ? (
                      <LoadingBlock label="Carregando bloqueios..." />
                    ) : (blackoutsQuery.data ?? []).length === 0 ? (
                      <EmptyState title="Nenhum bloqueio">
                        Registre feriados, manutenção ou horários vendidos fora do JOGA.
                      </EmptyState>
                    ) : (
                      <ul className="schedule-list">
                        {(blackoutsQuery.data ?? []).map((item) => (
                          <li key={item.id} className="schedule-row">
                            <span>
                              <strong>{item.reason}</strong>
                              <small>
                                {formatDate(item.starts_at)} — {formatDate(item.ends_at)}
                                {item.external_reference ? ` · ${item.external_reference}` : ""}
                              </small>
                            </span>
                            <button
                              type="button"
                              className="button button--small button--danger"
                              disabled={busy}
                              onClick={() => deleteBlackoutMutation.mutate(item)}
                            >
                              Remover
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}

                    <form className="form form--inline" onSubmit={createBlackout}>
                      <h3>Novo bloqueio</h3>
                      <div className="form-row">
                        <label className="field">
                          <span>Início</span>
                          <input
                            type="datetime-local"
                            value={blackoutStart}
                            onChange={(event) => setBlackoutStart(event.target.value)}
                            required
                          />
                        </label>
                        <label className="field">
                          <span>Fim</span>
                          <input
                            type="datetime-local"
                            value={blackoutEnd}
                            onChange={(event) => setBlackoutEnd(event.target.value)}
                            required
                          />
                        </label>
                      </div>
                      <label className="field">
                        <span>Motivo</span>
                        <input
                          type="text"
                          value={blackoutReason}
                          onChange={(event) => setBlackoutReason(event.target.value)}
                          maxLength={200}
                          placeholder="Feriado, manutenção, reserva externa..."
                          required
                        />
                      </label>
                      <label className="field">
                        <span>Referência externa (opcional)</span>
                        <input
                          type="text"
                          value={blackoutReference}
                          onChange={(event) => setBlackoutReference(event.target.value)}
                          maxLength={120}
                        />
                      </label>
                      <button type="submit" className="button button--primary" disabled={busy}>
                        Adicionar bloqueio
                      </button>
                    </form>
                  </div>
                </>
              )}
            </div>
          </section>
        ) : (
          <section className="stack">
            <div className="card">
              <div className="section-heading">
                <div>
                  <h2>Fotos do estabelecimento</h2>
                  <p className="muted">
                    Sem fotos de pessoas. Toda foto passa por revisão antes de ser publicada.
                  </p>
                </div>
              </div>

              <form className="form form--inline" onSubmit={uploadPhoto}>
                <div className="form-row">
                  <label className="field">
                    <span>Arquivo</span>
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={(event) => setPhotoFile(event.target.files?.[0] ?? null)}
                      required
                    />
                  </label>
                  <label className="field">
                    <span>Quadra (opcional)</span>
                    <select
                      value={photoSpaceId}
                      onChange={(event) => setPhotoSpaceId(event.target.value)}
                    >
                      <option value="">Estabelecimento</option>
                      {spaces.map((space) => (
                        <option key={space.id} value={space.id}>
                          {space.name}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
                <label className="field">
                  <span>Legenda</span>
                  <input
                    type="text"
                    value={photoCaption}
                    onChange={(event) => setPhotoCaption(event.target.value)}
                    maxLength={160}
                    placeholder="Quadra coberta ao anoitecer"
                  />
                </label>
                <button type="submit" className="button button--primary" disabled={busy}>
                  Enviar foto
                </button>
              </form>
            </div>

            <div className="card">
              <h2>Fotos enviadas</h2>
              {photosQuery.isPending ? (
                <LoadingBlock label="Carregando fotos..." />
              ) : photos.length === 0 ? (
                <EmptyState title="Nenhuma foto">
                  Envie a primeira foto da quadra ou do estabelecimento.
                </EmptyState>
              ) : (
                <ul className="photo-grid">
                  {photos.map((photo) => (
                    <li key={`${photo.id}:${photo.status}`} className="photo-card">
                      <PhotoThumb photo={photo} />
                      <div className="photo-card__body">
                        <strong>{photo.caption || "Sem legenda"}</strong>
                        <PhotoStatus photo={photo} />
                        <small>
                          {photo.width}×{photo.height} · {(photo.size_bytes / 1024).toFixed(0)} kB
                        </small>
                        {photo.rejection_reason ? (
                          <small className="muted">Motivo: {photo.rejection_reason}</small>
                        ) : null}
                        <div className="photo-card__actions">
                          {canReview && photo.status === "PENDING" ? (
                            <>
                              <button
                                type="button"
                                className="button button--small"
                                disabled={busy}
                                onClick={() => reviewPhoto(photo, "APPROVED")}
                              >
                                Aprovar
                              </button>
                              <button
                                type="button"
                                className="button button--small button--danger"
                                disabled={busy}
                                onClick={() => reviewPhoto(photo, "REJECTED")}
                              >
                                Rejeitar
                              </button>
                            </>
                          ) : null}
                          <button
                            type="button"
                            className="button button--small button--danger"
                            disabled={busy}
                            onClick={() => {
                              if (window.confirm("Remover esta foto?")) {
                                removePhotoMutation.mutate(photo);
                              }
                            }}
                          >
                            Remover
                          </button>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
