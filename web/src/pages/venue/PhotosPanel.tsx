import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, type FormEvent } from "react";

import { EmptyState, ErrorNotice, SkeletonList } from "../../components/Feedback";
import { Field, SelectField, TextField } from "../../components/ui/Field";
import { PhotoIcon, PlusIcon } from "../../components/ui/Icons";
import { ConfirmDialog, ReasonDialog } from "../../components/ui/Modal";
import { SectionHeading } from "../../components/ui/PageHeader";
import { useToast } from "../../components/ui/toast-context";
import { api } from "../../lib/api";
import { formatError, requestIdOf } from "../../lib/format";
import { queryKeys } from "../../lib/query";
import { photoFileError } from "../../lib/validation";
import type { VenuePhoto } from "../../types";

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

  if (failed) {
    return (
      <div className="photo-thumb photo-thumb--empty">
        <PhotoIcon size={22} />
        Falha ao carregar
      </div>
    );
  }
  if (!url) {
    return <div className="photo-thumb photo-thumb--empty skeleton" aria-label="Carregando foto" />;
  }
  return <img className="photo-thumb" src={url} alt={photo.caption ?? "Foto da quadra"} />;
}

function PhotoStatus({ photo }: { photo: VenuePhoto }) {
  const labels: Record<VenuePhoto["status"], string> = {
    PENDING: "Em revisão",
    APPROVED: "Aprovada",
    REJECTED: "Rejeitada",
    REMOVED: "Removida",
  };
  const tone: Record<VenuePhoto["status"], string> = {
    PENDING: "warning",
    APPROVED: "success",
    REJECTED: "danger",
    REMOVED: "muted",
  };
  return <span className={`badge badge--${tone[photo.status]}`}>{labels[photo.status]}</span>;
}

export function PhotosPanel({
  organization,
  venue,
  spaces,
  photos,
  canReview,
  loading,
  error,
  onRetry,
}: {
  organization: { id: string };
  venue: { id: string };
  spaces: Array<{ id: string; name: string }>;
  photos: VenuePhoto[];
  canReview: boolean;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [photoCaption, setPhotoCaption] = useState("");
  const [photoSpaceId, setPhotoSpaceId] = useState("");
  const [fileError, setFileError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [filter, setFilter] = useState<"all" | VenuePhoto["status"]>("all");
  const [rejectTarget, setRejectTarget] = useState<VenuePhoto | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [rejectError, setRejectError] = useState<string | null>(null);
  const [removeTarget, setRemoveTarget] = useState<VenuePhoto | null>(null);

  const previewUrl = useMemo(
    () => (photoFile ? URL.createObjectURL(photoFile) : null),
    [photoFile],
  );

  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    },
    [previewUrl],
  );

  const invalidatePhotos = () => {
    void queryClient.invalidateQueries({ queryKey: queryKeys.photos(organization.id, venue.id) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.audit(organization.id) });
  };

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!photoFile) throw new Error("Selecione uma foto.");
      return api.uploadPhoto(organization.id, venue.id, {
        file: photoFile,
        caption: photoCaption.trim() || undefined,
        spaceId: photoSpaceId || undefined,
      });
    },
    onSuccess: () => {
      setPhotoFile(null);
      setPhotoCaption("");
      setPhotoSpaceId("");
      setFileError(null);
      setActionError(null);
      toast.push({
        title: "Foto enviada para revisão",
        description:
          "A imagem só é publicada depois da aprovação de proprietário ou administrador.",
      });
      invalidatePhotos();
    },
    onError: (caught) => setActionError(caught),
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
    }) => api.reviewPhoto(organization.id, venue.id, photo.id, decision, reason),
    onSuccess: (_photo, variables) => {
      setRejectTarget(null);
      setRejectReason("");
      setRejectError(null);
      setActionError(null);
      toast.push({
        title: variables.decision === "APPROVED" ? "Foto aprovada" : "Foto rejeitada",
        description:
          variables.decision === "APPROVED"
            ? "A foto passa a ser exibida conforme a revisão."
            : "O motivo da rejeição fica registrado para o estabelecimento.",
      });
      invalidatePhotos();
    },
    onError: (caught, variables) => {
      setActionError(caught);
      if (variables.decision === "APPROVED") {
        toast.push({
          title: "Não foi possível aprovar a foto",
          description: formatError(caught),
          tone: "error",
          requestId: requestIdOf(caught),
        });
      }
    },
  });

  const removeMutation = useMutation({
    mutationFn: (photo: VenuePhoto) => api.removePhoto(organization.id, venue.id, photo.id),
    onSuccess: () => {
      setRemoveTarget(null);
      setActionError(null);
      toast.push({ title: "Foto removida" });
      invalidatePhotos();
    },
    onError: (caught) => setActionError(caught),
  });

  function chooseFile(file: File | null) {
    setFileError(null);
    setActionError(null);
    if (!file) {
      setPhotoFile(null);
      return;
    }
    const validation = photoFileError(file);
    if (validation) {
      setFileError(validation);
      setPhotoFile(null);
      return;
    }
    setPhotoFile(file);
  }

  function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!photoFile) {
      setFileError("Selecione uma foto para enviar.");
      document.getElementById("photo-file")?.focus();
      return;
    }
    uploadMutation.mutate();
  }

  function approve(photo: VenuePhoto) {
    setActionError(null);
    reviewMutation.mutate({ photo, decision: "APPROVED" });
  }

  function openReject(photo: VenuePhoto) {
    setActionError(null);
    setRejectTarget(photo);
    setRejectReason("");
    setRejectError(null);
  }

  function confirmReject() {
    if (!rejectTarget) return;
    if (!rejectReason.trim()) {
      setRejectError("Informe o motivo da rejeição.");
      return;
    }
    if (rejectReason.trim().length > 200) {
      setRejectError("O motivo deve ter no máximo 200 caracteres.");
      return;
    }
    reviewMutation.mutate({
      photo: rejectTarget,
      decision: "REJECTED",
      reason: rejectReason.trim(),
    });
  }

  const filtered = useMemo(
    () => (filter === "all" ? photos : photos.filter((photo) => photo.status === filter)),
    [filter, photos],
  );

  const displayError = error ?? actionError;

  return (
    <section className="stack">
      <div className="card card--form">
        <SectionHeading
          title="Enviar foto"
          description="Sem fotos de pessoas. Toda imagem passa por revisão antes de ser publicada."
        />
        <form className="form" onSubmit={upload} noValidate>
          <Field
            id="photo-file"
            label="Arquivo"
            hint="JPEG, PNG ou WebP, até 5 MB e dimensões entre 200 e 4000 px. Metadados são removidos no servidor."
            error={fileError}
            required
          >
            <input
              id="photo-file"
              className="input input--file"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(event) => chooseFile(event.target.files?.[0] ?? null)}
              aria-invalid={fileError ? true : undefined}
              aria-describedby={fileError ? "photo-file-error" : "photo-file-hint"}
              required
            />
          </Field>

          {photoFile ? (
            <div className="upload-preview">
              {previewUrl ? (
                <img
                  className="upload-preview__image"
                  src={previewUrl}
                  alt="Prévia da foto escolhida"
                />
              ) : null}
              <div className="upload-preview__body">
                <strong>{photoFile.name}</strong>
                <small>
                  {(photoFile.size / 1024).toFixed(0)} kB · {photoFile.type}
                </small>
                <button
                  type="button"
                  className="button button--small button--ghost"
                  onClick={() => chooseFile(null)}
                >
                  Remover seleção
                </button>
              </div>
            </div>
          ) : null}

          <div className="form-row">
            <SelectField
              id="photo-space"
              label="Quadra (opcional)"
              value={photoSpaceId}
              onChange={(event) => setPhotoSpaceId(event.target.value)}
              hint="Sem quadra, a foto representa o estabelecimento."
            >
              <option value="">Estabelecimento</option>
              {spaces.map((space) => (
                <option key={space.id} value={space.id}>
                  {space.name}
                </option>
              ))}
            </SelectField>
            <TextField
              id="photo-caption"
              label="Legenda"
              value={photoCaption}
              onChange={(event) => setPhotoCaption(event.target.value)}
              hint="Opcional. Até 160 caracteres."
              maxLength={160}
              placeholder="Quadra coberta ao anoitecer"
            />
          </div>

          {displayError ? (
            <ErrorNotice
              message={formatError(displayError)}
              requestId={requestIdOf(displayError)}
              onRetry={error ? onRetry : undefined}
            />
          ) : null}

          <button
            type="submit"
            className="button button--primary"
            disabled={uploadMutation.isPending || !photoFile}
            aria-busy={uploadMutation.isPending || undefined}
          >
            {uploadMutation.isPending ? "Enviando..." : "Enviar foto para revisão"}
          </button>
        </form>
      </div>

      <div className="card">
        <SectionHeading
          title="Fotos enviadas"
          description="Aprovação e rejeição ficam registradas na auditoria."
        />

        <div className="segmented" role="group" aria-label="Filtrar fotos">
          {(
            [
              ["all", "Todas", photos.length],
              [
                "PENDING",
                "Em revisão",
                photos.filter((photo) => photo.status === "PENDING").length,
              ],
              [
                "APPROVED",
                "Aprovadas",
                photos.filter((photo) => photo.status === "APPROVED").length,
              ],
              [
                "REJECTED",
                "Rejeitadas",
                photos.filter((photo) => photo.status === "REJECTED").length,
              ],
            ] as const
          ).map(([value, label, count]) => (
            <button
              key={value}
              type="button"
              className={filter === value ? "segmented__item is-active" : "segmented__item"}
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
            >
              {label}
              <span className="segmented__count">{count}</span>
            </button>
          ))}
        </div>

        {loading ? (
          <SkeletonList rows={2} label="Carregando fotos..." />
        ) : filtered.length === 0 ? (
          <EmptyState
            title={photos.length === 0 ? "Nenhuma foto" : "Nenhuma foto neste filtro"}
            icon={<PhotoIcon size={28} />}
            action={
              photos.length === 0 ? (
                <button
                  type="button"
                  className="button button--primary"
                  onClick={() => document.getElementById("photo-file")?.focus()}
                >
                  <PlusIcon size={16} />
                  Enviar primeira foto
                </button>
              ) : undefined
            }
          >
            {photos.length === 0
              ? "Envie a primeira foto da quadra ou do estabelecimento."
              : "Ajuste o filtro para ver outras fotos."}
          </EmptyState>
        ) : (
          <ul className="photo-grid">
            {filtered.map((photo) => (
              <li key={`${photo.id}:${photo.status}`} className="photo-card">
                <PhotoThumb photo={photo} />
                <div className="photo-card__body">
                  <strong>{photo.caption || "Sem legenda"}</strong>
                  <div className="photo-card__meta">
                    <PhotoStatus photo={photo} />
                    <small>
                      {photo.width}×{photo.height} · {(photo.size_bytes / 1024).toFixed(0)} kB
                    </small>
                  </div>
                  {photo.rejection_reason ? (
                    <small className="photo-card__reason">Motivo: {photo.rejection_reason}</small>
                  ) : null}
                  <div className="photo-card__actions">
                    {canReview && photo.status === "PENDING" ? (
                      <>
                        <button
                          type="button"
                          className="button button--small button--primary"
                          disabled={reviewMutation.isPending}
                          onClick={() => approve(photo)}
                        >
                          Aprovar
                        </button>
                        <button
                          type="button"
                          className="button button--small button--danger"
                          disabled={reviewMutation.isPending}
                          onClick={() => openReject(photo)}
                        >
                          Rejeitar
                        </button>
                      </>
                    ) : null}
                    <button
                      type="button"
                      className="button button--small button--ghost"
                      onClick={() => {
                        setActionError(null);
                        setRemoveTarget(photo);
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

      <ReasonDialog
        open={Boolean(rejectTarget)}
        title="Rejeitar foto"
        description="Explique o motivo. A justificativa fica registrada e visível para o estabelecimento."
        label="Motivo da rejeição"
        value={rejectReason}
        onChange={(value) => {
          setRejectReason(value);
          if (rejectError) setRejectError(null);
        }}
        error={rejectError}
        maxLength={200}
        confirmLabel="Rejeitar foto"
        tone="danger"
        busy={reviewMutation.isPending}
        onConfirm={confirmReject}
        onClose={() => {
          setRejectTarget(null);
          setRejectReason("");
          setRejectError(null);
          setActionError(null);
        }}
      >
        {actionError ? (
          <ErrorNotice message={formatError(actionError)} requestId={requestIdOf(actionError)} />
        ) : null}
      </ReasonDialog>

      <ConfirmDialog
        open={Boolean(removeTarget)}
        title="Remover foto?"
        description="A foto deixa de ser exibida. A remoção é registrada na auditoria e o arquivo é removido do armazenamento."
        tone="danger"
        confirmLabel="Remover foto"
        busy={removeMutation.isPending}
        onConfirm={() => {
          if (removeTarget) removeMutation.mutate(removeTarget);
        }}
        onClose={() => {
          setRemoveTarget(null);
          setActionError(null);
        }}
      >
        {actionError ? (
          <ErrorNotice message={formatError(actionError)} requestId={requestIdOf(actionError)} />
        ) : null}
      </ConfirmDialog>
    </section>
  );
}
