// @ts-check
import { io } from "socket.io-client";

/** @typedef {import("socket.io-client").Socket<import("../types/events").ServerToClientEvents>} ClientSocket */

/** @type {ClientSocket | undefined} */
let socket;

export function getSocket() {
  if (!socket) {
    socket = io("/", {
      transports: ["websocket", "polling"],
      withCredentials: true
    });
  }
  return socket;
}
