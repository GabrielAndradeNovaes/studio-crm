import * as React from "react";
import { Eraser, PenLine, Type } from "lucide-react";
import { Button, Input, Label } from "./primitives";

interface SignaturePadProps {
  value: string;
  onChange: (payload: string) => void;
  signerLabel?: string;
}

/**
 * Captura de assinatura híbrida (Canvas Touch/Mouse com Pointer Events + Confirmação Nominal acessível).
 */
export function SignaturePad({
  value,
  onChange,
  signerLabel = "Assinatura do Cliente / Responsável",
}: SignaturePadProps) {
  const [mode, setMode] = React.useState<"draw" | "typed">("draw");
  const [typedName, setTypedName] = React.useState("");
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const drawingRef = React.useRef(false);

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    onChange("");
  };

  const getPoint = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    };
  };

  const handlePointerDown = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.setPointerCapture(e.pointerId);
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    drawingRef.current = true;
    const { x, y } = getPoint(e);
    ctx.strokeStyle = "#0f172a";
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(x, y);
  };

  const handlePointerMove = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const { x, y } = getPoint(e);
    ctx.lineTo(x, y);
    ctx.stroke();
  };

  const handlePointerUp = () => {
    if (!drawingRef.current) return;
    drawingRef.current = false;
    const canvas = canvasRef.current;
    if (!canvas) return;
    onChange(canvas.toDataURL("image/png"));
  };

  return (
    <div className="space-y-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium text-foreground">
          {signerLabel} *
        </span>
        <div className="inline-flex rounded-md border border-border bg-secondary p-0.5">
          <button
            type="button"
            onClick={() => {
              setMode("draw");
              onChange("");
            }}
            className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium ${
              mode === "draw"
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground"
            }`}
          >
            <PenLine className="h-3.5 w-3.5" aria-hidden="true" />
            Desenhar na tela
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("typed");
              onChange(typedName.trim() ? `ASSINATURA NOMINAL: ${typedName.trim()}` : "");
            }}
            className={`inline-flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium ${
              mode === "typed"
                ? "bg-card text-foreground shadow-sm"
                : "text-muted-foreground"
            }`}
          >
            <Type className="h-3.5 w-3.5" aria-hidden="true" />
            Confirmação nominal
          </button>
        </div>
      </div>

      {mode === "draw" ? (
        <div className="space-y-2">
          <div className="overflow-hidden rounded-lg border-2 border-dashed border-slate-300 bg-white">
            <canvas
              ref={canvasRef}
              width={560}
              height={170}
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerUp}
              onPointerCancel={handlePointerUp}
              style={{ touchAction: "none" }}
              aria-label="Área de desenho da assinatura"
              className="h-40 w-full cursor-crosshair"
            />
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Assine com o dedo (celular/tablet) ou mouse.</span>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={clearCanvas}
              disabled={!value}
            >
              <Eraser className="h-3.5 w-3.5" aria-hidden="true" />
              Limpar traço
            </Button>
          </div>
        </div>
      ) : (
        <div>
          <Label htmlFor="nominal-signature" className="sr-only">
            Digite o nome completo para assinar eletronicamente
          </Label>
          <Input
            id="nominal-signature"
            required
            minLength={3}
            value={typedName}
            onChange={(e) => {
              const next = e.target.value;
              setTypedName(next);
              onChange(next.trim() ? `ASSINATURA NOMINAL: ${next.trim()}` : "");
            }}
            placeholder="Digite o nome completo do signatário para confirmar"
          />
        </div>
      )}
    </div>
  );
}
