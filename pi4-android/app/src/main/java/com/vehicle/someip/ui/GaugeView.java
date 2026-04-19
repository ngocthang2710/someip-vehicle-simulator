package com.vehicle.someip.ui;

import android.content.Context;
import android.graphics.*;
import android.util.AttributeSet;
import android.view.View;

/**
 * Custom analog gauge view — hiển thị speedometer / tachometer.
 * Vẽ bằng Canvas API, không dùng external library.
 */
public class GaugeView extends View {

    private float mValue    = 0f;
    private float mMaxValue = 200f;
    private float mRedZoneStart = Float.MAX_VALUE;
    private String mUnit  = "";
    private String mLabel = "";

    // Angles: 225° to -45° (270° sweep)
    private static final float ANGLE_START = 225f;
    private static final float ANGLE_SWEEP = 270f;

    // Paints
    private final Paint mArcPaint      = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mRedZonePaint  = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mNeedlePaint   = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mCenterPaint   = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mTextPaint     = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mValuePaint    = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mTickPaint     = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint mBgPaint       = new Paint(Paint.ANTI_ALIAS_FLAG);

    private final RectF mArcRect = new RectF();

    public GaugeView(Context ctx) { this(ctx, null); }
    public GaugeView(Context ctx, AttributeSet attrs) {
        super(ctx, attrs);
        init();
    }

    private void init() {
        // Background
        mBgPaint.setColor(0xFF1A1A2E);
        mBgPaint.setStyle(Paint.Style.FILL);

        // Arc track
        mArcPaint.setColor(0xFF2D2D44);
        mArcPaint.setStyle(Paint.Style.STROKE);
        mArcPaint.setStrokeCap(Paint.Cap.ROUND);

        // Red zone arc
        mRedZonePaint.setColor(0xFFFF3B30);
        mRedZonePaint.setStyle(Paint.Style.STROKE);
        mRedZonePaint.setStrokeCap(Paint.Cap.ROUND);

        // Needle
        mNeedlePaint.setColor(0xFFFF6B35);
        mNeedlePaint.setStyle(Paint.Style.STROKE);
        mNeedlePaint.setStrokeCap(Paint.Cap.ROUND);

        // Center dot
        mCenterPaint.setColor(0xFFFF6B35);
        mCenterPaint.setStyle(Paint.Style.FILL);

        // Tick marks
        mTickPaint.setColor(0xFF6B7280);
        mTickPaint.setStyle(Paint.Style.STROKE);

        // Label text
        mTextPaint.setColor(0xFF9CA3AF);
        mTextPaint.setTextAlign(Paint.Align.CENTER);
        mTextPaint.setTypeface(Typeface.create("monospace", Typeface.BOLD));

        // Value text
        mValuePaint.setColor(0xFFFFFFFF);
        mValuePaint.setTextAlign(Paint.Align.CENTER);
        mValuePaint.setTypeface(Typeface.create("monospace", Typeface.BOLD));
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        int w = getWidth();
        int h = getHeight();
        float cx = w / 2f;
        float cy = h / 2f;
        float radius = Math.min(cx, cy) * 0.85f;
        float strokeW = radius * 0.12f;

        // Background circle
        canvas.drawCircle(cx, cy, radius + strokeW, mBgPaint);

        // Arc setup
        mArcRect.set(cx - radius, cy - radius, cx + radius, cy + radius);
        mArcPaint.setStrokeWidth(strokeW);
        mRedZonePaint.setStrokeWidth(strokeW);

        // Background arc (full track)
        canvas.drawArc(mArcRect, ANGLE_START, ANGLE_SWEEP, false, mArcPaint);

        // Red zone arc
        if (mRedZoneStart < mMaxValue) {
            float redStart = ANGLE_START + (mRedZoneStart / mMaxValue) * ANGLE_SWEEP;
            float redSweep = ANGLE_SWEEP - (mRedZoneStart / mMaxValue) * ANGLE_SWEEP;
            canvas.drawArc(mArcRect, redStart, redSweep, false, mRedZonePaint);
        }

        // Value arc (active)
        float valueFraction = Math.min(1f, mValue / mMaxValue);
        float valueSweep = valueFraction * ANGLE_SWEEP;
        Paint activePaint = new Paint(mArcPaint);
        activePaint.setColor(valueFraction > 0.85f ? 0xFFFF3B30 : 0xFF00D4AA);
        activePaint.setStrokeWidth(strokeW);
        activePaint.setStrokeCap(Paint.Cap.ROUND);
        canvas.drawArc(mArcRect, ANGLE_START, valueSweep, false, activePaint);

        // Tick marks
        drawTicks(canvas, cx, cy, radius, strokeW);

        // Needle
        float needleAngle = (float) Math.toRadians(ANGLE_START + valueSweep);
        float needleLen = radius * 0.72f;
        float nx = cx + needleLen * (float) Math.cos(needleAngle);
        float ny = cy + needleLen * (float) Math.sin(needleAngle);
        mNeedlePaint.setStrokeWidth(strokeW * 0.3f);
        canvas.drawLine(cx, cy, nx, ny, mNeedlePaint);

        // Center dot
        canvas.drawCircle(cx, cy, strokeW * 0.6f, mCenterPaint);

        // Value text
        mValuePaint.setTextSize(radius * 0.35f);
        canvas.drawText(String.format("%.0f", mValue), cx, cy + radius * 0.35f, mValuePaint);

        // Unit text
        mTextPaint.setTextSize(radius * 0.18f);
        canvas.drawText(mUnit, cx, cy + radius * 0.58f, mTextPaint);

        // Label text (top)
        mTextPaint.setTextSize(radius * 0.16f);
        canvas.drawText(mLabel, cx, cy - radius * 0.55f, mTextPaint);
    }

    private void drawTicks(Canvas canvas, float cx, float cy, float radius, float strokeW) {
        int tickCount = 10;
        mTickPaint.setStrokeWidth(strokeW * 0.15f);
        for (int i = 0; i <= tickCount; i++) {
            float angle = (float) Math.toRadians(ANGLE_START + (i / (float) tickCount) * ANGLE_SWEEP);
            float outerR = radius * 0.95f;
            float innerR = (i % 2 == 0) ? radius * 0.78f : radius * 0.85f;
            canvas.drawLine(
                cx + innerR * (float) Math.cos(angle),
                cy + innerR * (float) Math.sin(angle),
                cx + outerR * (float) Math.cos(angle),
                cy + outerR * (float) Math.sin(angle),
                mTickPaint);
        }
    }

    // ─── Public API ───────────────────────────────────────────────────────────
    public void setValue(float value) {
        mValue = Math.max(0f, Math.min(mMaxValue, value));
        invalidate();
    }

    public void setMaxValue(float max)        { mMaxValue = max; invalidate(); }
    public void setUnit(String unit)           { mUnit = unit; invalidate(); }
    public void setLabel(String label)         { mLabel = label; invalidate(); }
    public void setRedZoneStart(float start)   { mRedZoneStart = start; invalidate(); }
}
