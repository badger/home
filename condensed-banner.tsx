/*---------------------------------------------------------------------------------------------
 *  Copyright (c) Microsoft Corporation. All rights reserved.
 *--------------------------------------------------------------------------------------------*/

import React, { useEffect, useState } from "react";
import { Box, Text, useIsScreenReaderEnabled } from "ink";
import { useTheme } from "../themes/ThemeContext";
import { Config } from "../dataPersistence/config";
import { RunnerLogger } from "../../runner";
import { NoopLogger } from "../../runner/logger/noop";
import { ANSIColors, Theme, hasDarkTerminalBackground } from "../themes";

export function CondensedBanner({
    animationComplete = () => {},
    completed = false,
    bannerConfig,
    loggerOverride,
}: {
    animationComplete?: () => void;
    completed?: boolean;
    bannerConfig?: "always" | "once" | "never";
    loggerOverride?: RunnerLogger;
}) {
    const { theme } = useTheme();
    const logger = loggerOverride ?? new NoopLogger();
    const [frameIdx, setFrameIdx] = useState(completed ? totalFrames - 1 : 0);
    const isScreenReaderEnabled = useIsScreenReaderEnabled();

    useEffect(() => {
        // Don't animate the banner for screen readers as it is extremely noisy
        // Don't animate the banner for users who don't want it as you can't make everyone happy
        if (isScreenReaderEnabled || bannerConfig === "never") {
            animationComplete();
            return;
        }

        if (frameIdx >= totalFrames - 1) {
            // If banner config is "once", update it to "never" after animation completes
            if (bannerConfig === "once") {
                void (async () => {
                    try {
                        await Config.writeKey("banner", "never");
                    } catch (error) {
                        logger.error(`Failed to update banner preference: ${error}`);
                    }
                })();
            }
            animationComplete();
            return; // Don't set up a timer if we're already at the last frame
        }

        const currentInterval = frameIntervals[frameIdx];
        const id = setTimeout(() => {
            setFrameIdx((i) => i + 1);
        }, currentInterval);

        return () => {
            clearTimeout(id);
        };
    }, [frameIdx, bannerConfig]);

    if (isScreenReaderEnabled || !bannerConfig || bannerConfig === "never") {
        return null; // No text fallback for condensed banner
    }

    const frameContent = getFrameContent(frameIdx);
    const currentFrame = getBannerAnimation().frames[Math.min(frameIdx, totalFrames - 1)];

    return (
        <Box flexDirection="column" alignItems="flex-start">
            {frameContent.map((line, rowIndex) => {
                const truncatedLine = line.length > 80 ? line.substring(0, 80) : line;
                const coloredChars = Array.from(truncatedLine).map((char, colIndex) => {
                    const color = getCharacterColor(rowIndex, colIndex, currentFrame, theme);
                    return { char, color };
                });

                // Group consecutive characters with the same color
                const segments: Array<{ text: string; color: string }> = [];
                let currentSegment = { text: "", color: coloredChars[0]?.color || theme.COPILOT };

                coloredChars.forEach(({ char, color }) => {
                    if (color === currentSegment.color) {
                        currentSegment.text += char;
                    } else {
                        if (currentSegment.text) segments.push(currentSegment);
                        currentSegment = { text: char, color };
                    }
                });
                if (currentSegment.text) segments.push(currentSegment);

                return (
                    <Text key={rowIndex} wrap="truncate">
                        {segments.map((segment, segIndex) => (
                            <Text key={segIndex} color={segment.color}>
                                {segment.text}
                            </Text>
                        ))}
                    </Text>
                );
            })}
        </Box>
    );
}

type AnimationElements = "border" | "eyes" | "head" | "goggles" | "shine";

type AnimationTheme = Record<AnimationElements, ANSIColors>;

const ANIMATION_ANSI_DARK: AnimationTheme = {
    border: "white",
    eyes: "greenBright",
    head: "magentaBright",
    goggles: "cyanBright",
    shine: "whiteBright",
};

const ANIMATION_ANSI_LIGHT: AnimationTheme = {
    border: "blackBright",
    eyes: "green",
    head: "magenta",
    goggles: "cyan",
    shine: "whiteBright",
};

/**
 * Represents a single animation frame with metadata
 */
interface AnimationFrame {
    title: string;
    duration: number;
    content: string;
    colors?: Record<string, AnimationElements>; // Map of "row,col" positions to animation elements
}

/**
 * Represents the complete animation with metadata and frames
 */
interface Animation {
    metadata: {
        id: string;
        name: string;
        description: string;
    };
    frames: AnimationFrame[];
}

/**
 * Gets the appropriate theme-aware color for a character at a specific position
 */
function getCharacterColor(row: number, col: number, frame: AnimationFrame, theme: Theme): ANSIColors {
    if (!frame.colors) return theme.COPILOT;

    const element = frame.colors[`${row},${col}`];
    if (element === undefined) return theme.FG;

    const colorMapping = hasDarkTerminalBackground ? ANIMATION_ANSI_DARK : ANIMATION_ANSI_LIGHT;
    return colorMapping[element] || theme.COPILOT;
}

/**
 * Creates the condensed CLI banner animation (narrower, no text)
 */
export function createBannerAnimation(): Animation {
    const frames: AnimationFrame[] = [
        {
            title: "Frame 1",
            duration: 80,
            content: `
┌──                                           ──┐
│                             ▄██████▄          │
                          ▄█▀▀▀▀▀██▀▀▀▀▀█▄
    █████┐ ██┐     ██┐   ▐█      ▐▌      █▌
   ██┌───┘ ██│     ██│   ▐█▄    ▄██▄    ▄█▌
   ██│     ██│     ██│  ▄▄███████▀▀███████▄▄
   ██│     ██│     ██│ ████     ▄  ▄     ████
   └█████┐ ██████┐ ██│ ████     █  █     ████
    └────┘ └─────┘ └─┘ ▀███▄            ▄███▀
│                          ▀▀████████████▀▀     │
└──                                           ──┘`,
            colors: {
                "1,0": "border",
                "1,1": "border",
                "1,2": "border",
                "1,44": "border",
                "1,45": "border",
                "1,46": "border",
                "2,0": "border",
                "2,29": "head",
                "2,30": "head",
                "2,31": "head",
                "2,32": "head",
                "2,33": "head",
                "2,34": "head",
                "2,35": "head",
                "2,36": "head",
                "2,46": "border",
                "3,26": "goggles",
                "3,27": "goggles",
                "3,28": "goggles",
                "3,29": "goggles",
                "3,30": "goggles",
                "3,31": "goggles",
                "3,32": "goggles",
                "3,33": "goggles",
                "3,34": "goggles",
                "3,35": "goggles",
                "3,36": "goggles",
                "3,37": "goggles",
                "3,38": "goggles",
                "3,39": "goggles",
                "3,40": "goggles",
                "3,41": "goggles",
                "4,25": "goggles",
                "4,26": "goggles",
                "4,33": "goggles",
                "4,34": "goggles",
                "4,41": "goggles",
                "4,42": "goggles",
                "5,25": "goggles",
                "5,26": "goggles",
                "5,27": "goggles",
                "5,32": "goggles",
                "5,33": "goggles",
                "5,34": "goggles",
                "5,35": "goggles",
                "5,40": "goggles",
                "5,41": "goggles",
                "5,42": "goggles",
                "6,24": "head",
                "6,25": "head",
                "6,26": "head",
                "6,27": "goggles",
                "6,28": "goggles",
                "6,29": "goggles",
                "6,30": "goggles",
                "6,31": "goggles",
                "6,32": "goggles",
                "6,33": "goggles",
                "6,34": "goggles",
                "6,35": "goggles",
                "6,36": "goggles",
                "6,37": "goggles",
                "6,38": "goggles",
                "6,39": "goggles",
                "6,40": "goggles",
                "6,41": "head",
                "6,42": "head",
                "6,43": "head",
                "7,23": "head",
                "7,24": "head",
                "7,25": "head",
                "7,26": "head",
                "7,32": "eyes",
                "7,35": "eyes",
                "7,41": "head",
                "7,42": "head",
                "7,43": "head",
                "7,44": "head",
                "8,23": "head",
                "8,24": "head",
                "8,25": "head",
                "8,26": "head",
                "8,32": "eyes",
                "8,35": "eyes",
                "8,41": "head",
                "8,42": "head",
                "8,43": "head",
                "8,44": "head",
                "9,23": "head",
                "9,24": "head",
                "9,25": "head",
                "9,26": "head",
                "9,27": "head",
                "9,40": "head",
                "9,41": "head",
                "9,42": "head",
                "9,43": "head",
                "9,44": "head",
                "10,0": "border",
                "10,26": "head",
                "10,27": "head",
                "10,28": "head",
                "10,29": "head",
                "10,30": "head",
                "10,31": "head",
                "10,32": "head",
                "10,33": "head",
                "10,34": "head",
                "10,35": "head",
                "10,36": "head",
                "10,37": "head",
                "10,38": "head",
                "10,39": "head",
                "10,40": "head",
                "10,41": "head",
                "10,46": "border",
                "11,0": "border",
                "11,1": "border",
                "11,2": "border",
                "11,44": "border",
                "11,45": "border",
                "11,46": "border",
            },
        },
        {
            title: "Frame 2 - Eye blink start",
            duration: 70,
            content: `
┌──                                           ──┐
│                             ▄██████▄          │
                          ▄█▀▀▀▀▀██▀▀▀▀▀█▄
    █████┐ ██┐     ██┐   ▐█ ██   ▐▌      █▌
   ██┌───┘ ██│     ██│   ▐█▄█   ▄██▄    ▄█▌
   ██│     ██│     ██│  ▄▄███████▀▀███████▄▄
   ██│     ██│     ██│ ████     ▄  ▄     ████
   └█████┐ ██████┐ ██│ ████     █  █     ████
    └────┘ └─────┘ └─┘ ▀███▄            ▄███▀
│                          ▀▀████████████▀▀     │
└──                                           ──┘`,
            colors: {
                "1,0": "border",
                "1,1": "border",
                "1,2": "border",
                "1,44": "border",
                "1,45": "border",
                "1,46": "border",
                "2,0": "border",
                "2,29": "head",
                "2,30": "head",
                "2,31": "head",
                "2,32": "head",
                "2,33": "head",
                "2,34": "head",
                "2,35": "head",
                "2,36": "head",
                "2,46": "border",
                "3,26": "goggles",
                "3,27": "goggles",
                "3,28": "goggles",
                "3,29": "goggles",
                "3,30": "goggles",
                "3,31": "goggles",
                "3,32": "goggles",
                "3,33": "goggles",
                "3,34": "goggles",
                "3,35": "goggles",
                "3,36": "goggles",
                "3,37": "goggles",
                "3,38": "goggles",
                "3,39": "goggles",
                "3,40": "goggles",
                "3,41": "goggles",
                "4,25": "goggles",
                "4,26": "goggles",
                "4,28": "shine",
                "4,29": "shine",
                "4,33": "goggles",
                "4,34": "goggles",
                "4,41": "goggles",
                "4,42": "goggles",
                "5,25": "goggles",
                "5,26": "goggles",
                "5,27": "goggles",
                "5,28": "shine",
                "5,32": "goggles",
                "5,33": "goggles",
                "5,34": "goggles",
                "5,35": "goggles",
                "5,40": "goggles",
                "5,41": "goggles",
                "5,42": "goggles",
                "6,24": "head",
                "6,25": "head",
                "6,26": "head",
                "6,27": "goggles",
                "6,28": "goggles",
                "6,29": "goggles",
                "6,30": "goggles",
                "6,31": "goggles",
                "6,32": "goggles",
                "6,33": "goggles",
                "6,34": "goggles",
                "6,35": "goggles",
                "6,36": "goggles",
                "6,37": "goggles",
                "6,38": "goggles",
                "6,39": "goggles",
                "6,40": "goggles",
                "6,41": "head",
                "6,42": "head",
                "6,43": "head",
                "7,23": "head",
                "7,24": "head",
                "7,25": "head",
                "7,26": "head",
                "7,32": "eyes",
                "7,35": "eyes",
                "7,41": "head",
                "7,42": "head",
                "7,43": "head",
                "7,44": "head",
                "8,23": "head",
                "8,24": "head",
                "8,25": "head",
                "8,26": "head",
                "8,32": "eyes",
                "8,35": "eyes",
                "8,41": "head",
                "8,42": "head",
                "8,43": "head",
                "8,44": "head",
                "9,23": "head",
                "9,24": "head",
                "9,25": "head",
                "9,26": "head",
                "9,27": "head",
                "9,40": "head",
                "9,41": "head",
                "9,42": "head",
                "9,43": "head",
                "9,44": "head",
                "10,0": "border",
                "10,26": "head",
                "10,27": "head",
                "10,28": "head",
                "10,29": "head",
                "10,30": "head",
                "10,31": "head",
                "10,32": "head",
                "10,33": "head",
                "10,34": "head",
                "10,35": "head",
                "10,36": "head",
                "10,37": "head",
                "10,38": "head",
                "10,39": "head",
                "10,40": "head",
                "10,41": "head",
                "10,46": "border",
                "11,0": "border",
                "11,1": "border",
                "11,2": "border",
                "11,44": "border",
                "11,45": "border",
                "11,46": "border",
            },
        },
        {
            title: "Frame 3 - Eye blink continue",
            duration: 70,
            content: `
┌──                                           ──┐
│                             ▄██████▄          │
                          ▄█▀▀▀▀▀██▀▀▀▀▀█▄
    █████┐ ██┐     ██┐   ▐█     █▐▌█     █▌
   ██┌───┘ ██│     ██│   ▐█▄   █▄██▄    ▄█▌
   ██│     ██│     ██│  ▄▄███████▀▀███████▄▄
   ██│     ██│     ██│ ████     ▄  ▄     ████
   └█████┐ ██████┐ ██│ ████     █  █     ████
    └────┘ └─────┘ └─┘ ▀███▄            ▄███▀
│                          ▀▀████████████▀▀     │
└──                                           ──┘`,
            colors: {
                "1,0": "border",
                "1,1": "border",
                "1,2": "border",
                "1,44": "border",
                "1,45": "border",
                "1,46": "border",
                "2,0": "border",
                "2,29": "head",
                "2,30": "head",
                "2,31": "head",
                "2,32": "head",
                "2,33": "head",
                "2,34": "head",
                "2,35": "head",
                "2,36": "head",
                "2,46": "border",
                "3,26": "goggles",
                "3,27": "goggles",
                "3,28": "goggles",
                "3,29": "goggles",
                "3,30": "goggles",
                "3,31": "goggles",
                "3,32": "goggles",
                "3,33": "goggles",
                "3,34": "goggles",
                "3,35": "goggles",
                "3,36": "goggles",
                "3,37": "goggles",
                "3,38": "goggles",
                "3,39": "goggles",
                "3,40": "goggles",
                "3,41": "goggles",
                "4,25": "goggles",
                "4,26": "goggles",
                "4,32": "shine",
                "4,33": "goggles",
                "4,34": "goggles",
                "4,35": "shine",
                "4,41": "goggles",
                "4,42": "goggles",
                "5,25": "goggles",
                "5,26": "goggles",
                "5,27": "goggles",
                "5,32": "goggles",
                "5,33": "goggles",
                "5,34": "goggles",
                "5,35": "goggles",
                "5,40": "goggles",
                "5,41": "goggles",
                "5,42": "goggles",
                "6,24": "head",
                "6,25": "head",
                "6,26": "head",
                "6,27": "goggles",
                "6,28": "goggles",
                "6,29": "goggles",
                "6,30": "goggles",
                "6,31": "goggles",
                "6,32": "goggles",
                "6,33": "goggles",
                "6,34": "goggles",
                "6,35": "goggles",
                "6,36": "goggles",
                "6,37": "goggles",
                "6,38": "goggles",
                "6,39": "goggles",
                "6,40": "goggles",
                "6,41": "head",
                "6,42": "head",
                "6,43": "head",
                "7,23": "head",
                "7,24": "head",
                "7,25": "head",
                "7,26": "head",
                "7,32": "eyes",
                "7,35": "eyes",
                "7,41": "head",
                "7,42": "head",
                "7,43": "head",
                "7,44": "head",
                "8,23": "head",
                "8,24": "head",
                "8,25": "head",
                "8,26": "head",
                "8,32": "eyes",
                "8,35": "eyes",
                "8,41": "head",
                "8,42": "head",
                "8,43": "head",
                "8,44": "head",
                "9,23": "head",
                "9,24": "head",
                "9,25": "head",
                "9,26": "head",
                "9,27": "head",
                "9,40": "head",
                "9,41": "head",
                "9,42": "head",
                "9,43": "head",
                "9,44": "head",
                "10,0": "border",
                "10,26": "head",
                "10,27": "head",
                "10,28": "head",
                "10,29": "head",
                "10,30": "head",
                "10,31": "head",
                "10,32": "head",
                "10,33": "head",
                "10,34": "head",
                "10,35": "head",
                "10,36": "head",
                "10,37": "head",
                "10,38": "head",
                "10,39": "head",
                "10,40": "head",
                "10,41": "head",
                "10,46": "border",
                "11,0": "border",
                "11,1": "border",
                "11,2": "border",
                "11,44": "border",
                "11,45": "border",
                "11,46": "border",
            },
        },
        {
            title: "Frame 4 - Eye blink finish",
            duration: 70,
            content: `
┌──                                           ──┐
│                             ▄██████▄          │
                          ▄█▀▀▀▀▀██▀▀▀▀▀█▄
    █████┐ ██┐     ██┐   ▐█      ▐▌    ███▌
   ██┌───┘ ██│     ██│   ▐█▄    ▄██▄  ██▄█▌
   ██│     ██│     ██│  ▄▄███████▀▀███████▄▄
   ██│     ██│     ██│ ████     ▄  ▄     ████
   └█████┐ ██████┐ ██│ ████     █  █     ████
    └────┘ └─────┘ └─┘ ▀███▄            ▄███▀
│                          ▀▀████████████▀▀     │
└──                                           ──┘`,
            colors: {
                "1,0": "border",
                "1,1": "border",
                "1,2": "border",
                "1,44": "border",
                "1,45": "border",
                "1,46": "border",
                "2,0": "border",
                "2,29": "head",
                "2,30": "head",
                "2,31": "head",
                "2,32": "head",
                "2,33": "head",
                "2,34": "head",
                "2,35": "head",
                "2,36": "head",
                "2,46": "border",
                "3,26": "goggles",
                "3,27": "goggles",
                "3,28": "goggles",
                "3,29": "goggles",
                "3,30": "goggles",
                "3,31": "goggles",
                "3,32": "goggles",
                "3,33": "goggles",
                "3,34": "goggles",
                "3,35": "goggles",
                "3,36": "goggles",
                "3,37": "goggles",
                "3,38": "goggles",
                "3,39": "goggles",
                "3,40": "goggles",
                "3,41": "goggles",
                "4,25": "goggles",
                "4,26": "goggles",
                "4,33": "goggles",
                "4,34": "goggles",
                "4,39": "shine",
                "4,40": "shine",
                "4,41": "goggles",
                "4,42": "goggles",
                "5,25": "goggles",
                "5,26": "goggles",
                "5,27": "goggles",
                "5,32": "goggles",
                "5,33": "goggles",
                "5,34": "goggles",
                "5,35": "goggles",
                "5,38": "shine",
                "5,39": "shine",
                "5,40": "goggles",
                "5,41": "goggles",
                "5,42": "goggles",
                "6,24": "head",
                "6,25": "head",
                "6,26": "head",
                "6,27": "goggles",
                "6,28": "goggles",
                "6,29": "goggles",
                "6,30": "goggles",
                "6,31": "goggles",
                "6,32": "goggles",
                "6,33": "goggles",
                "6,34": "goggles",
                "6,35": "goggles",
                "6,36": "goggles",
                "6,37": "goggles",
                "6,38": "goggles",
                "6,39": "goggles",
                "6,40": "goggles",
                "6,41": "head",
                "6,42": "head",
                "6,43": "head",
                "7,23": "head",
                "7,24": "head",
                "7,25": "head",
                "7,26": "head",
                "7,32": "eyes",
                "7,35": "eyes",
                "7,41": "head",
                "7,42": "head",
                "7,43": "head",
                "7,44": "head",
                "8,23": "head",
                "8,24": "head",
                "8,25": "head",
                "8,26": "head",
                "8,32": "eyes",
                "8,35": "eyes",
                "8,41": "head",
                "8,42": "head",
                "8,43": "head",
                "8,44": "head",
                "9,23": "head",
                "9,24": "head",
                "9,25": "head",
                "9,26": "head",
                "9,27": "head",
                "9,40": "head",
                "9,41": "head",
                "9,42": "head",
                "9,43": "head",
                "9,44": "head",
                "10,0": "border",
                "10,26": "head",
                "10,27": "head",
                "10,28": "head",
                "10,29": "head",
                "10,30": "head",
                "10,31": "head",
                "10,32": "head",
                "10,33": "head",
                "10,34": "head",
                "10,35": "head",
                "10,36": "head",
                "10,37": "head",
                "10,38": "head",
                "10,39": "head",
                "10,40": "head",
                "10,41": "head",
                "10,46": "border",
                "11,0": "border",
                "11,1": "border",
                "11,2": "border",
                "11,44": "border",
                "11,45": "border",
                "11,46": "border",
            },
        },
        {
            title: "Frame 5 - Final",
            duration: 850,
            content: `
┌──                                           ──┐
│                             ▄██████▄          │
                          ▄█▀▀▀▀▀██▀▀▀▀▀█▄
    █████┐ ██┐     ██┐   ▐█      ▐▌      █▌
   ██┌───┘ ██│     ██│   ▐█▄    ▄██▄    ▄█▌
   ██│     ██│     ██│  ▄▄███████▀▀███████▄▄
   ██│     ██│     ██│ ████     ▄  ▄     ████
   └█████┐ ██████┐ ██│ ████     █  █     ████
    └────┘ └─────┘ └─┘ ▀███▄            ▄███▀
│                          ▀▀████████████▀▀     │
└──                                           ──┘`,
            colors: {
                "1,0": "border",
                "1,1": "border",
                "1,2": "border",
                "1,44": "border",
                "1,45": "border",
                "1,46": "border",
                "2,0": "border",
                "2,29": "head",
                "2,30": "head",
                "2,31": "head",
                "2,32": "head",
                "2,33": "head",
                "2,34": "head",
                "2,35": "head",
                "2,36": "head",
                "2,46": "border",
                "3,26": "goggles",
                "3,27": "goggles",
                "3,28": "goggles",
                "3,29": "goggles",
                "3,30": "goggles",
                "3,31": "goggles",
                "3,32": "goggles",
                "3,33": "goggles",
                "3,34": "goggles",
                "3,35": "goggles",
                "3,36": "goggles",
                "3,37": "goggles",
                "3,38": "goggles",
                "3,39": "goggles",
                "3,40": "goggles",
                "3,41": "goggles",
                "4,25": "goggles",
                "4,26": "goggles",
                "4,33": "goggles",
                "4,34": "goggles",
                "4,41": "goggles",
                "4,42": "goggles",
                "5,25": "goggles",
                "5,26": "goggles",
                "5,27": "goggles",
                "5,32": "goggles",
                "5,33": "goggles",
                "5,34": "goggles",
                "5,35": "goggles",
                "5,40": "goggles",
                "5,41": "goggles",
                "5,42": "goggles",
                "6,24": "head",
                "6,25": "head",
                "6,26": "head",
                "6,27": "goggles",
                "6,28": "goggles",
                "6,29": "goggles",
                "6,30": "goggles",
                "6,31": "goggles",
                "6,32": "goggles",
                "6,33": "goggles",
                "6,34": "goggles",
                "6,35": "goggles",
                "6,36": "goggles",
                "6,37": "goggles",
                "6,38": "goggles",
                "6,39": "goggles",
                "6,40": "goggles",
                "6,41": "head",
                "6,42": "head",
                "6,43": "head",
                "7,23": "head",
                "7,24": "head",
                "7,25": "head",
                "7,26": "head",
                "7,32": "eyes",
                "7,35": "eyes",
                "7,41": "head",
                "7,42": "head",
                "7,43": "head",
                "7,44": "head",
                "8,23": "head",
                "8,24": "head",
                "8,25": "head",
                "8,26": "head",
                "8,32": "eyes",
                "8,35": "eyes",
                "8,41": "head",
                "8,42": "head",
                "8,43": "head",
                "8,44": "head",
                "9,23": "head",
                "9,24": "head",
                "9,25": "head",
                "9,26": "head",
                "9,27": "head",
                "9,40": "head",
                "9,41": "head",
                "9,42": "head",
                "9,43": "head",
                "9,44": "head",
                "10,0": "border",
                "10,26": "head",
                "10,27": "head",
                "10,28": "head",
                "10,29": "head",
                "10,30": "head",
                "10,31": "head",
                "10,32": "head",
                "10,33": "head",
                "10,34": "head",
                "10,35": "head",
                "10,36": "head",
                "10,37": "head",
                "10,38": "head",
                "10,39": "head",
                "10,40": "head",
                "10,41": "head",
                "10,46": "border",
                "11,0": "border",
                "11,1": "border",
                "11,2": "border",
                "11,44": "border",
                "11,45": "border",
                "11,46": "border",
            },
        },
    ];

    return {
        metadata: {
            id: "condensed-cli-banner",
            name: "Condensed CLI banner",
            description: "Narrower banner animation without text, based on new-banner.txt",
        },
        frames,
    };
}

// Animation exports
const defaultBannerAnimation = createBannerAnimation();
export const frameIntervals = defaultBannerAnimation.frames.slice(0, -1).map((frame) => frame.duration);
export const totalFrames = defaultBannerAnimation.frames.length;

/**
 * Gets the frame content for a specific frame index
 */
export function getFrameContent(frameIdx: number): string[] {
    const animation = getBannerAnimation();
    const frame = animation.frames[Math.min(frameIdx, animation.frames.length - 1)];
    return frame.content.split("\n");
}

/**
 * Gets the complete animation object
 */
export function getBannerAnimation(): Animation {
    return defaultBannerAnimation;
}
